"""Behavior tests with temporary catalogs and fake SSH commands; no network access."""
import json
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'nk'
REAL_FZF = shutil.which('fzf')
CATALOG = '''[production]
web-prod | 192.0.2.10 | 22 | ubuntu | | billing-main
[development]
web-dev | 192.0.2.20 | 2222 | deploy | fixture-password | sandbox-demo
'''


class NookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nook-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.config = self.root / 'config'
        self.config.mkdir()
        self.catalog = self.config / 'servers.conf'
        self.catalog.write_text(CATALOG)
        (self.config / '.history').write_text('web-prod\n')
        self.env = dict(os.environ, NOOK_CONFIG_DIR=str(self.config),
                        NOOK_TEST_ROOT=str(self.root), PATH=str(self.bin),
                        NOOK_TEST_FZF='first')
        for command in ('bash', 'awk', 'cat', 'chmod', 'cp', 'cut', 'dirname',
                        'grep', 'head', 'hostname', 'mkdir', 'mktemp', 'mv',
                        'rm', 'sh', 'sort', 'touch'):
            (self.bin / command).symlink_to(shutil.which(command))
        for command in ('ssh', 'sshpass', 'ssh-copy-id', 'ssh-keygen'):
            self.stub(command, '''
import json, os, sys
from pathlib import Path
root = Path(os.environ['NOOK_TEST_ROOT'])
with (root / 'connections.jsonl').open('a') as f:
    f.write(json.dumps({'command': Path(sys.argv[0]).name, 'args': sys.argv[1:]}) + '\\n')
sys.exit(int(os.environ.get('NOOK_TEST_SSH_EXIT', '0')))
''')
        self.enable_fzf()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def enable_fzf(self):
        self.stub('fzf', '''
import json, os, subprocess, sys
from pathlib import Path
root = Path(os.environ['NOOK_TEST_ROOT'])
data = sys.stdin.read()
(root / 'fzf-input').write_text(data)
(root / 'fzf-args.json').write_text(json.dumps(sys.argv[1:]))
mode = os.environ['NOOK_TEST_FZF']
if mode == 'cancel': sys.exit(130)
if mode == 'no-match': sys.exit(1)
if mode == 'error':
    print('fzf test error', file=sys.stderr)
    sys.exit(2)
if mode == 'filter':
    result = subprocess.run([os.environ['NOOK_TEST_REAL_FZF'], *sys.argv[1:],
                             '--filter=' + os.environ['NOOK_TEST_QUERY']],
                            input=data, text=True, capture_output=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)
print(data.splitlines()[0])
''')

    def run_nk(self, *args, input='', **env):
        return subprocess.run(['/bin/bash', str(SCRIPT), *args], input=input,
                              text=True, capture_output=True, timeout=10,
                              env=dict(self.env, **env))

    def calls(self):
        log = self.root / 'connections.jsonl'
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def terminal_session(self, steps, columns=80):
        """Exercise the actual terminal protocol, including fzf's cursor query."""
        child, master = pty.fork()
        if child == 0:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 24, columns, 0, 0))
            os.execve('/bin/bash', ['/bin/bash', str(SCRIPT)],
                      dict(self.env, TERM='xterm-256color'))
        output = b''
        reaped = False

        def collect_output(timeout=0.1):
            nonlocal output
            ready, _, _ = select.select([master], [], [], timeout)
            if not ready:
                return b''
            try:
                chunk = os.read(master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    return b''
                raise
            output += chunk
            if b'\x1b[6n' in chunk:
                os.write(master, b'\x1b[1;1R')
            return chunk

        try:
            for expected, keys in steps:
                received = b''
                deadline = time.monotonic() + 5
                while expected not in received and time.monotonic() < deadline:
                    received += collect_output()
                self.assertIn(expected, received, repr(output[-3000:]))
                if keys:
                    os.write(master, keys)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                finished, status = os.waitpid(child, os.WNOHANG)
                if finished:
                    reaped = True
                    break
                collect_output()
            else:
                self.fail('terminal process did not exit')
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        finally:
            if not reaped:
                try:
                    os.kill(child, signal.SIGKILL)
                    os.waitpid(child, 0)
                except (ProcessLookupError, ChildProcessError):
                    pass
            os.close(master)
        return output

    def test_picker_keeps_empty_password_and_secrets_out_of_fzf(self):
        self.assert_ok(self.run_nk())
        self.assertEqual(self.calls()[0]['command'], 'ssh')
        self.assertEqual(self.calls()[0]['args'][-1], 'ubuntu@192.0.2.10')
        data = (self.root / 'fzf-input').read_text()
        self.assertNotIn('fixture-password', data)
        self.assertEqual(len(data.splitlines()), 2)
        self.assertTrue(all(len(line.split('\t')) == 2 for line in data.splitlines()))

    def test_exact_name_bypasses_picker(self):
        self.assert_ok(self.run_nk('web-prod'))
        self.assertFalse((self.root / 'fzf-input').exists())
        self.assertEqual(self.calls()[0]['command'], 'ssh')

    def test_saved_password_is_preserved(self):
        self.assert_ok(self.run_nk('web-dev'))
        self.assertEqual(self.calls()[0]['command'], 'sshpass')
        self.assertEqual(self.calls()[0]['args'][:3], ['-p', 'fixture-password', 'ssh'])
        self.assertEqual(self.calls()[0]['args'][-1], 'deploy@192.0.2.20')

    def test_ambiguous_exact_name_still_requires_selection(self):
        with self.catalog.open('a') as f:
            f.write('web-prod | 192.0.2.11 | 22 | ubuntu | | second server\n')
        self.assert_ok(self.run_nk('web-prod', NOOK_TEST_FZF='cancel'))
        self.assertTrue((self.root / 'fzf-input').exists())
        self.assertEqual(self.calls(), [])

    @unittest.skipUnless(REAL_FZF, 'real fzf is not installed')
    def test_real_fzf_searches_note_user_host_and_group(self):
        for query, destination in [('billing-main', 'ubuntu@192.0.2.10'),
                                   ('deploy', 'deploy@192.0.2.20'),
                                   ('192.0.2.10', 'ubuntu@192.0.2.10'),
                                   ('development', 'deploy@192.0.2.20')]:
            with self.subTest(query=query):
                self.assert_ok(self.run_nk(query, NOOK_TEST_FZF='filter',
                               NOOK_TEST_REAL_FZF=REAL_FZF, NOOK_TEST_QUERY=query))
                self.assertEqual(self.calls()[-1]['args'][-1], destination)

    def test_fallback_shows_choices_and_connects(self):
        (self.bin / 'fzf').unlink()
        result = self.run_nk(input='1\n')
        self.assert_ok(result)
        self.assertIn('1) web-prod', result.stderr)
        self.assertIn('Pick [1-2]', result.stderr)
        self.assertEqual(self.calls()[0]['args'][-1], 'ubuntu@192.0.2.10')
        self.assertNotIn('choose a server', result.stdout)

    def test_fallback_search_includes_user_and_keeps_password(self):
        (self.bin / 'fzf').unlink()
        self.assert_ok(self.run_nk('deploy', input='01\n'))
        self.assertEqual(self.calls()[0]['args'][:2], ['-p', 'fixture-password'])

    def test_cancel_is_successful_without_connecting(self):
        for command in ((), ('rm',), ('key',)):
            with self.subTest(command=command):
                self.assert_ok(self.run_nk(*command, NOOK_TEST_FZF='cancel'))
        (self.bin / 'fzf').unlink()
        self.assert_ok(self.run_nk(input='\n'))
        self.assertEqual(self.calls(), [])

    def test_picker_errors_are_visible(self):
        result = self.run_nk('unknown', NOOK_TEST_FZF='no-match')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no server matched', result.stderr)
        result = self.run_nk(NOOK_TEST_FZF='error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fzf test error', result.stderr)
        self.assertIn('doctor', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_quick_add_requires_only_address_and_name(self):
        result = self.run_nk('add', input='ssh ubuntu@example.com -p 2222\nmy-server\n')
        self.assert_ok(result)
        self.assertIn('Connect: nk my-server', result.stdout)
        self.assertNotIn('Group [', result.stderr)
        self.assertNotIn('Save password', result.stderr)
        self.assert_ok(self.run_nk('my-server'))
        self.assertEqual(self.calls()[0]['args'][-3:], ['-p', '2222', 'ubuntu@example.com'])

    def test_address_arguments_and_default_name(self):
        self.assert_ok(self.run_nk('add', 'deploy@example.com', '-p', '0022', input='\n'))
        self.assert_ok(self.run_nk('example.com'))
        self.assertEqual(self.calls()[0]['args'][-3:], ['-p', '22', 'deploy@example.com'])

    def test_ipv6_and_ssh_user_option(self):
        self.assert_ok(self.run_nk('add', 'ssh -l deploy -p2222 [2001:db8::1]', input='ipv6\n'))
        self.assert_ok(self.run_nk('ipv6'))
        self.assertEqual(self.calls()[0]['args'][-1], 'deploy@2001:db8::1')

    def test_advanced_add_preserves_literal_backslashes(self):
        password = r'test\backslash$word'
        result = self.run_nk('add', '--advanced', 'deploy@example.com',
                             input='advanced\nproduction\nliteral \\ note\n' + password + '\n')
        self.assert_ok(result)
        self.assert_ok(self.run_nk('advanced'))
        self.assertEqual(self.calls()[0]['args'][1], password)
        self.assertIn(r'literal \ note', self.catalog.read_text())
        self.assertEqual(self.catalog.stat().st_mode & 0o777, 0o600)

    def test_duplicate_name_is_rejected_without_writing(self):
        before = self.catalog.read_text()
        result = self.run_nk('add', 'example.com', input='web-prod\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(self.catalog.read_text(), before)

    def test_invalid_addresses_and_ports_are_rejected_without_writing(self):
        before = self.catalog.read_text()
        for address in ('host -p nope', 'host -p 0', 'host -p 65536', 'host -p -1',
                        'host -p 999999999999999999', 'ssh', 'ssh host -p',
                        'ssh -i key.pem host', 'ssh host uptime', 'host:2222',
                        'host|injected', 'ssh $(touch sentinel)', '@host', '   '):
            with self.subTest(address=address):
                result = self.run_nk('add', address, input='test\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('[x]', result.stderr)
                self.assertEqual(self.catalog.read_text(), before)
        self.assertEqual(self.calls(), [])

    def test_invalid_name_and_optional_fields_are_rejected(self):
        before = self.catalog.read_text()
        for name in ('#comment', '[group]', 'bad|name', 'list', 'help'):
            result = self.run_nk('add', 'example.com', input=name + '\n')
            self.assertNotEqual(result.returncode, 0)
        for inputs in ('test\nbad[group]\n', 'test\ndefault\nbad|note\n',
                       'test\ndefault\nnote\nbad|password\n',
                       'test\ndefault\nnote\n padded-password \n'):
            result = self.run_nk('add', '--advanced', 'example.com', input=inputs)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.catalog.read_text(), before)

    def test_invalid_existing_config_reports_line_and_edit_command(self):
        self.catalog.write_text('[default]\nbad | example.com | oops | root | | note\n')
        result = self.run_nk('bad')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('servers.conf:2', result.stderr)
        self.assertIn('nk edit', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_legacy_defaults_and_missing_final_newline(self):
        self.catalog.write_text('[default]\nold | example.com | | | | existing note')
        self.assert_ok(self.run_nk('old'))
        self.assertEqual(self.calls()[0]['args'][-3:], ['-p', '22', 'root@example.com'])

    def test_remove_only_selected_record_with_duplicate_names(self):
        self.catalog.write_text('[default]\nsame | a.example | | | |\nsame | b.example | | | |\n')
        self.assert_ok(self.run_nk('rm', input='y\n'))
        self.assertNotIn('a.example', self.catalog.read_text())
        self.assertIn('b.example', self.catalog.read_text())
        self.assertEqual(self.calls(), [])

    def test_preview_has_note_and_correct_recent_rank(self):
        result = self.run_nk('__preview', '1')
        self.assert_ok(result)
        self.assertIn('Recent: #1', result.stdout)
        self.assertIn('billing-main', result.stdout)
        self.assertNotIn('fixture-password', result.stdout)

    def test_empty_noninteractive_start_explains_next_step(self):
        self.catalog.unlink()
        result = self.run_nk()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('nk add', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_ssh_exit_status_is_preserved(self):
        result = self.run_nk('web-prod', NOOK_TEST_SSH_EXIT='255')
        self.assertEqual(result.returncode, 255)

    def test_name_with_spaces_can_be_used_directly(self):
        result = self.run_nk('add', 'example.com', input='my server\n')
        self.assert_ok(result)
        self.assertIn('Connect: nk my\\ server', result.stdout)
        self.assert_ok(self.run_nk('my server'))
        self.assertFalse((self.root / 'fzf-input').exists())

    def test_interactive_first_run_goes_straight_to_add(self):
        self.catalog.unlink()
        output = self.terminal_session([
            (b'Address (', b'ubuntu@example.com\r'),
            (b'Name [', b'first-server\r'),
            (b'[ok] Added first-server', b''),
        ])
        self.assertIn(b'No servers yet', output)
        self.assertIn('first-server', self.catalog.read_text())
        self.assertEqual(self.calls(), [])

    @unittest.skipUnless(REAL_FZF, 'real fzf is not installed')
    def test_real_picker_tab_and_enter_in_normal_and_narrow_terminals(self):
        (self.bin / 'fzf').unlink()
        (self.bin / 'fzf').symlink_to(REAL_FZF)
        for columns in (80, 48):
            with self.subTest(columns=columns):
                self.terminal_session([
                    (b'web-prod', b'\t'),
                    (b'Login:', b'\r'),
                    (b'[connect]', b''),
                ], columns=columns)
                self.assertEqual(self.calls()[-1]['args'][-1], 'ubuntu@192.0.2.10')

    @unittest.skipUnless(REAL_FZF, 'real fzf is not installed')
    def test_real_picker_escape_cancels(self):
        (self.bin / 'fzf').unlink()
        (self.bin / 'fzf').symlink_to(REAL_FZF)
        self.terminal_session([(b'web-prod', b'\x1b')])
        self.assertEqual(self.calls(), [])

    def test_local_install_uses_explicit_isolated_config(self):
        install_dir = self.root / 'installed-bin'
        config_dir = self.root / 'installed-config'
        result = subprocess.run(['/bin/bash', str(SCRIPT.parent / 'install.sh')],
                                text=True, capture_output=True, timeout=10,
                                env=dict(self.env, NOOK_INSTALL_DIR=str(install_dir),
                                         NOOK_CONFIG_DIR=str(config_dir)))
        self.assert_ok(result)
        self.assertEqual((install_dir / 'nk').read_bytes(), SCRIPT.read_bytes())
        self.assertIn('[default]', (config_dir / 'servers.conf').read_text())
        self.assertNotIn('web-prod', (config_dir / 'servers.conf').read_text())
        self.assertEqual((config_dir / 'servers.conf').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
