"""Service orchestration contract tests; no Docker daemon or real network needed.

Run on Ubuntu: python -m unittest discover -s tests/unit -p test_service_script.py
The fake Docker/curl programs verify command construction and error propagation.
They do not prove that container images boot or an SMTP provider delivers mail.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which('bash')
try:
    BASH_OK = bool(BASH) and subprocess.run(
        [BASH, '--version'], capture_output=True, timeout=10
    ).returncode == 0
except (OSError, subprocess.TimeoutExpired):
    BASH_OK = False


FAKE_DOCKER = '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['GNK_TEST_CALLS'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
services = ['postgres','redis','mailpit','backend','frontend','nginx']
if args[0] == 'info':
    sys.exit(1 if os.environ.get('FAKE_DOCKER_DOWN') else 0)
if args[0] == 'inspect':
    print('exited unhealthy' if os.environ.get('FAKE_UNHEALTHY') else 'running healthy')
elif 'version' in args:
    print('Docker Compose version v2.30.0')
elif 'config' in args and '--services' in args:
    print('\\n'.join(services))
elif 'ps' in args and '--quiet' in args:
    if not os.environ.get('FAKE_MISSING'):
        print('container-' + args[-1])
elif 'build' in args and os.environ.get('FAKE_BUILD_FAIL'):
    sys.exit(7)
'''

FAKE_CURL = '''#!/usr/bin/env python3
import os, sys
print(os.environ.get('FAKE_HTTP_CODE', '200'), end='')
'''


@unittest.skipUnless(BASH_OK and os.name != 'nt', 'Requires working Linux Bash and executable test doubles')
class ServiceScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gnk-service-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project with spaces'
        self.root.mkdir()
        for folder in ('deploy', 'service'):
            shutil.copytree(ROOT / folder, self.root / folder)
        for name in ('docker-compose.yml', 'docker-compose.prod.yml'):
            shutil.copy2(ROOT / name, self.root / name)
        self.env_path = self.root / '.env'
        self.env_path.write_text('JWT_SECRET=' + 'x' * 48 + '\nPOSTGRES_PASSWORD=database-test-password\nENVIRONMENT=development\nFRONTEND_URL=http://localhost:8080\n')
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        for name, content in [('docker', FAKE_DOCKER), ('curl', FAKE_CURL)]:
            p = self.bin / name
            p.write_text(content)
            p.chmod(0o755)
        self.calls = Path(self.temp.name) / 'calls.jsonl'
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith('GNK_') or key in ('ENVIRONMENT','FRONTEND_URL','JWT_SECRET','POSTGRES_PASSWORD'):
                self.env.pop(key)
        self.env.update(PATH=str(self.bin) + os.pathsep + self.env['PATH'], GNK_TEST_CALLS=str(self.calls))

    def run_service(self, *args, **overrides):
        return subprocess.run([BASH, str(self.root / 'deploy/gnk-service.sh'), *args],
                              cwd=self.temp.name, env={**self.env, **overrides},
                              text=True, capture_output=True, timeout=15)

    def docker_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_bash_syntax(self):
        for path in ('deploy/gnk-service.sh','service/gnk-service.sh'):
            result = subprocess.run([BASH, '-n', str(self.root / path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_waits_and_checks_services(self):
        result = self.run_service('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.docker_calls()
        self.assertTrue(any('up' in c and '--wait' in c for c in calls))
        self.assertEqual(sum(c[0] == 'inspect' for c in calls), 6)
        self.assertIn('/admin', result.stdout)
        self.assertIn('PASS /api/v1/health', result.stdout)

    def test_stop_never_removes_volumes(self):
        result = self.run_service('stop')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.docker_calls()
        self.assertTrue(any(c[-1] == 'stop' for c in calls))
        self.assertFalse(any('down' in c or '--volumes' in c or '-v' in c for c in calls))

    def test_build_does_not_start(self):
        self.assertEqual(self.run_service('build').returncode, 0)
        self.assertTrue(any(c[-1] == 'build' for c in self.docker_calls()))
        self.assertFalse(any('up' in c for c in self.docker_calls()))

    def test_failed_build_does_not_deploy(self):
        result = self.run_service('deploy', FAKE_BUILD_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('up' in c for c in self.docker_calls()))

    def test_production_deploy_and_urls(self):
        result = self.run_service('deploy', GNK_ENV='production', GNK_PUBLIC_URL='https://gnk.example')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.docker_calls()
        self.assertTrue(any(str(self.root / 'docker-compose.prod.yml') in c for c in calls))
        build = next(i for i,c in enumerate(calls) if 'build' in c)
        up = next(i for i,c in enumerate(calls) if 'up' in c)
        self.assertLess(build, up)
        self.assertIn('https://gnk.example/admin', result.stdout)
        self.assertNotIn('http://127.0.0.1:8025', result.stdout)

    def test_health_detects_container_and_http_failures(self):
        for override in ({'FAKE_UNHEALTHY':'1'}, {'FAKE_MISSING':'1'}, {'FAKE_HTTP_CODE':'503'}):
            result = self.run_service('health', **override)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('FAIL', result.stdout)

    def test_status_lists_urls_and_detects_stopped_services(self):
        result = self.run_service('status', FAKE_UNHEALTHY='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('/api/v1/admin/system-health', result.stdout)
        self.assertTrue(any('ps' in c and '--all' in c for c in self.docker_calls()))

    def test_logs_service_filter_and_snapshot(self):
        result = self.run_service('logs', 'backend', 'nginx', GNK_LOG_FOLLOW='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        log_call = next(c for c in self.docker_calls() if 'logs' in c)
        self.assertNotIn('--follow', log_call)
        self.assertEqual(log_call[-2:], ['backend','nginx'])
        self.assertNotEqual(self.run_service('logs', '--help').returncode, 0)

    def test_urls_work_without_docker_or_env_file(self):
        self.env_path.unlink()
        result = self.run_service('urls', FAKE_DOCKER_DOWN='1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('http://localhost:8080/admin', result.stdout)
        self.assertEqual(self.docker_calls(), [])

    def test_missing_env_and_placeholder_secret_are_rejected(self):
        self.env_path.unlink()
        self.assertNotEqual(self.run_service('start').returncode, 0)
        self.env_path.write_text('JWT_SECRET=replace-with-something\nPOSTGRES_PASSWORD=replace-with-something\n')
        result = self.run_service('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('replace-with-something', result.stderr)

    def test_dotenv_is_data_not_executable_code(self):
        marker = self.root / 'should-not-exist'
        with self.env_path.open('a') as out:
            out.write(f'UNUSED=$(touch "{marker}")\n')
        self.assertEqual(self.run_service('urls').returncode, 0)
        self.assertFalse(marker.exists())

    def test_invalid_command_and_arguments(self):
        self.assertNotEqual(self.run_service('destroy').returncode, 0)
        self.assertNotEqual(self.run_service('stop', 'postgres').returncode, 0)
        self.assertNotEqual(self.run_service('health', GNK_WAIT_TIMEOUT='bad').returncode, 0)


if __name__ == '__main__':
    unittest.main()
