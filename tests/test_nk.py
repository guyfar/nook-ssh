"""Behavior tests with temporary catalogs and fake SSH commands; no network access."""
import json
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
import unicodedata

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
        for command in ('bash', 'awk', 'cat', 'chmod', 'cp', 'cut', 'date', 'dirname',
                        'grep', 'head', 'hostname', 'mkdir', 'mktemp', 'mv',
                        'rm', 'sh', 'sort', 'stty', 'touch'):
            (self.bin / command).symlink_to(shutil.which(command))
        if shutil.which('column'):
            (self.bin / 'column').symlink_to(shutil.which('column'))
        for command in ('ssh', 'sshpass', 'ssh-copy-id', 'ssh-keygen'):
            self.stub(command, '''
import json, os, sys
from pathlib import Path
root = Path(os.environ['NOOK_TEST_ROOT'])
with (root / 'connections.jsonl').open('a') as f:
    f.write(json.dumps({'command': Path(sys.argv[0]).name, 'args': sys.argv[1:]}) + '\\n')
if Path(sys.argv[0]).name == 'ssh-copy-id' or 'ssh-copy-id' in sys.argv[1:]:
    if os.environ.get('NOOK_TEST_KEY_EXIT'):
        print('Permission denied (publickey,password).', file=sys.stderr)
        sys.exit(int(os.environ['NOOK_TEST_KEY_EXIT']))
sys.exit(int(os.environ.get('NOOK_TEST_SSH_EXIT', '0')))
''')
        self.stub('nc', '''
import os, sys
if sys.argv[-2] == os.environ.get('NOOK_TEST_UNREACHABLE'):
    print('Connection refused', file=sys.stderr)
    sys.exit(1)
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
lines = data.splitlines()
if '--header-lines=1' in sys.argv: lines = lines[1:]
# Simulate --expect: an action key prints its name before the selected row.
action = os.environ.get('NOOK_TEST_ACTION', '')
if action:
    print(action)
print(lines[0])
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

    def terminal_session(self, steps, columns=80, args=(), expected_status=0, extra_env=None):
        """Exercise the actual terminal protocol, including fzf's cursor query."""
        child, master = pty.fork()
        if child == 0:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 24, columns, 0, 0))
            os.execve('/bin/bash', ['/bin/bash', str(SCRIPT), *args],
                      dict(self.env, TERM='xterm-256color', **(extra_env or {})))
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
            cursor = 0
            for expected, keys in steps:
                deadline = time.monotonic() + 5
                # Search cumulative output from a monotonic cursor so text that
                # arrives early (fzf redraws eagerly) is never missed, while a
                # repeated marker is still matched in order.
                while expected not in output[cursor:] and time.monotonic() < deadline:
                    collect_output()
                self.assertIn(expected, output[cursor:], repr(output[-3000:]))
                cursor = output.index(expected, cursor) + len(expected)
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
            self.assertEqual(os.waitstatus_to_exitcode(status), expected_status)
            self.assertTrue(termios.tcgetattr(master)[3] & termios.ECHO,
                            'terminal echo was not restored: ' + repr(output[-1500:]))
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
        self.assertEqual(len(data.splitlines()), 3)
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
        self.assertRegex(result.stderr, r'1\)\s+web-prod')
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

    def test_preview_has_target_note_and_same_ssh_command_as_connection(self):
        result = self.run_nk('__preview', '1')
        self.assert_ok(result)
        self.assertIn('web-prod [production]', result.stdout)
        self.assertIn('ubuntu@192.0.2.10:22', result.stdout)
        self.assertIn('billing-main', result.stdout)
        self.assertNotIn('fixture-password', result.stdout)
        self.assert_ok(self.run_nk('web-prod'))
        command = result.stdout.split('SSH command:\n', 1)[1].strip()
        self.assertEqual(shlex.split(command), ['ssh', *self.calls()[0]['args']])

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

    @unittest.skipUnless(shutil.which('column'), 'column is not installed')
    def test_columns_align_cjk_names_and_keep_full_targets(self):
        self.catalog.write_text('[production]\n生产主机 | long-server-name.example.com | 2222 | ubuntu | | 中文备注\n'
                                '[development]\nweb-dev | 192.0.2.20 | 22 | deploy | | sandbox\n')
        self.assert_ok(self.run_nk(NOOK_TEST_FZF='cancel'))
        rows = (self.root / 'fzf-input').read_text().splitlines()[1:]
        group_offsets = []
        target_offsets = []
        def width(value):
            return sum(0 if unicodedata.combining(char) else
                       2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
                       for char in value)
        for row in rows:
            display = row.split('\t', 1)[1]
            group_offsets.append(width(display[:display.index('[')]))
            target = 'ubuntu@' if '生产主机' in display else 'deploy@'
            target_offsets.append(width(display[:display.index(target)]))
        self.assertEqual(group_offsets[0], group_offsets[1])
        self.assertEqual(target_offsets[0], target_offsets[1])
        self.assertIn('ubuntu@long-server-name.example.com:2222', '\n'.join(rows))
        self.assertIn('deploy@192.0.2.20:22', '\n'.join(rows))

    def test_picker_works_without_column(self):
        column = self.bin / 'column'
        if column.exists(): column.unlink()
        self.assert_ok(self.run_nk())
        self.assertEqual(self.calls()[0]['args'][-1], 'ubuntu@192.0.2.10')

    def test_list_labels_groups_and_complete_targets(self):
        result = self.run_nk('list')
        self.assert_ok(result)
        self.assertIn('USER@HOST:PORT', result.stdout)
        self.assertIn('[production]', result.stdout)
        self.assertIn('deploy@192.0.2.20:2222', result.stdout)
        self.assertNotIn('fixture-password', result.stdout)

    def test_interactive_port_and_name_correction_keeps_destination(self):
        output = self.terminal_session([
            (b'Port [22]:', b'2222\r'),
            (b'Name [', b'web-prod\r'),
            (b'already exists', b'corrected\r'),
            (b'[ok] Added corrected', b''),
        ], args=('add', 'ssh deploy@example.com -p nope'))
        self.assertNotIn(b'Address (', output)
        self.assert_ok(self.run_nk('corrected'))
        self.assertEqual(self.calls()[0]['args'][-3:], ['-p', '2222', 'deploy@example.com'])

    def test_interactive_bad_address_can_be_corrected(self):
        self.terminal_session([
            (b'Address (', b'ubuntu@example.com\r'),
            (b'Name [', b'corrected-address\r'),
            (b'[ok] Added corrected-address', b''),
        ], args=('add', 'ssh -i unsupported-key example.com'))
        self.assert_ok(self.run_nk('corrected-address'))
        self.assertEqual(self.calls()[0]['args'][-1], 'ubuntu@example.com')

    def test_interactive_optional_fields_retry_independently(self):
        output = self.terminal_session([
            (b'Name [', b'advanced-retry\r'),
            (b'Group [', b'bad[group]\r'),
            (b'group cannot contain', b'production\r'),
            (b'Note [', b'bad|note\r'),
            (b'Note cannot contain', b'kept note\r'),
            (b'Save password', b'bad|password\r'),
            (b'Save password', b'kept-password\r'),
            (b'[ok] Added advanced-retry', b''),
        ], args=('add', '--advanced', 'deploy@example.com -p 2222'))
        self.assertEqual(output.count(b'Name ['), 1)
        self.assertIn(b'Password cannot contain', output)
        self.assertNotIn(b'bad|password', output)
        self.assertNotIn(b'kept-password', output)
        self.assertIn('kept note', self.catalog.read_text())
        self.assert_ok(self.run_nk('advanced-retry'))
        self.assertEqual(self.calls()[0]['args'][1], 'kept-password')

    def test_end_of_input_during_retry_saves_nothing(self):
        before = self.catalog.read_text()
        self.terminal_session([(b'Port [22]:', b'\x04')],
                              args=('add', 'ubuntu@example.com -p nope'), expected_status=1)
        self.assertEqual(self.catalog.read_text(), before)

    def test_end_of_input_at_password_restores_terminal(self):
        before = self.catalog.read_text()
        self.terminal_session([
            (b'Name [', b'cancel-password\r'),
            (b'Group [', b'\r'),
            (b'Note [', b'\r'),
            (b'Save password', b'\x04'),
        ], args=('add', '--advanced', 'ubuntu@example.com'), expected_status=1)
        self.assertEqual(self.catalog.read_text(), before)

    def test_interrupt_at_password_restores_terminal(self):
        before = self.catalog.read_text()
        self.terminal_session([
            (b'Name [', b'cancel-password\r'),
            (b'Group [', b'\r'),
            (b'Note [', b'\r'),
            (b'Save password', b'\x03'),
        ], args=('add', '--advanced', 'ubuntu@example.com'), expected_status=130)
        self.assertEqual(self.catalog.read_text(), before)

    def test_key_setup_preserves_original_error_and_exit_status(self):
        result = self.run_nk('key', NOOK_TEST_KEY_EXIT='255')
        self.assertEqual(result.returncode, 255)
        self.assertIn('Permission denied (publickey,password).', result.stderr)
        self.assertIn('Check login with: ssh', result.stderr)
        self.assertIn('ubuntu@192.0.2.10', result.stderr)
        self.assertNotIn('[ok]', result.stdout)

    def test_key_setup_reports_missing_dependency_before_any_key_action(self):
        (self.bin / 'ssh-copy-id').unlink()
        result = self.run_nk('key')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ssh-copy-id is not installed', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_preview_does_not_promise_saved_password_without_sshpass(self):
        (self.bin / 'sshpass').unlink()
        result = self.run_nk('__preview', '2')
        self.assert_ok(result)
        self.assertIn('sshpass is not installed', result.stdout)
        self.assertNotIn('Login: saved password', result.stdout)
        self.assertNotIn('fixture-password', result.stdout)

    def test_port_checks_distinguish_tcp_reachability_from_login(self):
        result = self.run_nk('ping', NOOK_TEST_UNREACHABLE='192.0.2.20')
        self.assertEqual(result.returncode, 1)
        self.assertIn('SSH login is not tested', result.stdout)
        self.assertIn('192.0.2.10:22  [ok] SSH port reachable', result.stdout)
        self.assertIn('192.0.2.20:2222  [x] SSH port not reachable', result.stdout)
        self.assertIn('Connection refused', result.stderr)
        self.assertNotIn('offline', result.stdout)
        self.assertNotIn('online', result.stdout)
        self.assertEqual(self.calls(), [])

    def test_missing_nc_is_not_reported_as_unreachable_servers(self):
        (self.bin / 'nc').unlink()
        result = self.run_nk('ping')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('nc is not installed', result.stderr)
        self.assertNotIn('not reachable', result.stdout)

    def test_all_reachable_ports_exit_successfully(self):
        self.assert_ok(self.run_nk('ping'))

    @unittest.skipUnless(REAL_FZF, 'real fzf is not installed')
    def test_long_notes_can_be_scrolled_to_ssh_command(self):
        self.catalog.write_text('[production]\nweb-prod | 192.0.2.10 | 22 | ubuntu | | '
                                + 'operational-note ' * 50 + '\n')
        (self.bin / 'fzf').unlink()
        (self.bin / 'fzf').symlink_to(REAL_FZF)
        self.terminal_session([
            (b'web-prod', b'\t'),
            (b'Note:', b'\x1b[1;3B' * 40),
            (b'SSH command:', b'\r'),
            (b'[connect]', b''),
        ], columns=48)

    def test_history_records_timestamp_and_reads_legacy_lines(self):
        (self.config / '.history').write_text('web-dev\n')
        self.assert_ok(self.run_nk('web-prod'))
        history = (self.config / '.history').read_text().splitlines()
        self.assertEqual(history[0].split('\t')[0], 'web-prod')
        self.assertRegex(history[0].split('\t')[1], r'^[0-9]+$')
        # Legacy name-only lines are preserved verbatim until next connected.
        self.assertIn('web-dev', (self.config / '.history').read_text().splitlines()[1])

    def test_failed_connect_offers_recovery_only_in_a_terminal(self):
        # Non-interactive runs must not block on the recovery prompt.
        result = self.run_nk('web-prod', NOOK_TEST_SSH_EXIT='255')
        self.assertEqual(result.returncode, 255)
        self.assertNotIn('Choice:', result.stderr)
        self.assertNotIn('Could not connect', result.stderr)

    def test_failed_connect_prompts_in_a_terminal(self):
        output = self.terminal_session([
            (b'Could not connect', b'\r'),
        ], args=('web-prod',), expected_status=255, extra_env={'NOOK_TEST_SSH_EXIT': '255'})
        self.assertIn(b'[p] check port reachability', output)
        self.assertIn(b'Choice:', output)

    def test_picker_actions_stay_in_the_picker(self):
        # Actions must not exit the picker: no --expect (which exits on each key)
        # and no become (which replaces fzf). Everything runs via execute, with
        # side-effect-free actions silent or preview-only.
        self.assert_ok(self.run_nk(NOOK_TEST_FZF='cancel'))
        args = json.loads((self.root / 'fzf-args.json').read_text())
        self.assertFalse([a for a in args if a.startswith('--expect')])
        binds = [a for a in args if a.startswith('--bind=')][0]
        self.assertIn('ctrl-e:toggle-preview', binds)
        self.assertIn('execute-silent', binds)
        self.assertNotIn('become', binds)
        for key in ('ctrl-e', 'ctrl-p', 'ctrl-y', 'ctrl-k', 'ctrl-d', 'ctrl-r'):
            self.assertIn(key, binds)

    def test_picker_action_does_not_connect(self):
        # A keybind action must never fall through to a connection.
        self.assert_ok(self.run_nk('__action-silent', 'ping', '1'))
        self.assert_ok(self.run_nk('__action', 'delete', '1', input='n\n\n'))
        self.assertEqual(self.calls(), [])

    def test_picker_action_delete_removes_the_selected_server(self):
        self.assert_ok(self.run_nk('__action', 'delete', '1', input='y\n\n'))
        self.assertNotIn('web-prod', self.catalog.read_text())
        self.assertIn('web-dev', self.catalog.read_text())
        self.assertEqual(self.calls(), [])

    def test_picker_shows_last_used_column(self):
        now = int(time.time())
        (self.config / '.history').write_text('web-prod\t%d\nweb-dev\t%d\n'
                                              % (now - 7200, now - 3 * 86400))
        self.assert_ok(self.run_nk(NOOK_TEST_FZF='cancel'))
        rows = (self.root / 'fzf-input').read_text()
        self.assertIn('2h', rows)
        self.assertIn('3d', rows)

    def test_picker_shows_status_and_stale_marker(self):
        now = int(time.time())
        (self.config / '.status').write_text('web-prod\tup\t%d\t\nweb-dev\tdown\t%d\t\n'
                                             % (now, now - 90000))
        self.assert_ok(self.run_nk(NOOK_TEST_FZF='cancel'))
        rows = (self.root / 'fzf-input').read_text()
        self.assertIn('up', rows)
        self.assertIn('down*', rows)
        self.assertNotIn('fixture-password', rows)

    def test_ping_records_status_cache_for_picker(self):
        self.assertNotEqual(self.run_nk('ping', NOOK_TEST_UNREACHABLE='192.0.2.20').returncode, 0)
        status = (self.config / '.status').read_text()
        self.assertIn('web-prod\tup\t', status)
        self.assertIn('web-dev\tdown\t', status)
        self.assertIn('ctrl-r', self.run_nk('ping').stdout)

    def test_ping_refresh_updates_cache_quietly(self):
        self.assert_ok(self.run_nk('__ping-refresh'))
        status = (self.config / '.status').read_text()
        self.assertIn('web-prod\tup\t', status)

    def test_cancel_does_not_create_status_file(self):
        # Status stays a cache: merely opening the picker must not write it.
        self.assert_ok(self.run_nk(NOOK_TEST_FZF='cancel'))
        self.assertEqual((self.config / '.status').read_text(), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
