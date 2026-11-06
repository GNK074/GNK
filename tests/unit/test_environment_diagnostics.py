"""Deployment diagnostics identify configuration failures without leaking inputs."""
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def run_validation(**overrides):
    env={**os.environ,'APP_ENV':'testing','ENVIRONMENT':'testing','JWT_SECRET_KEY':'offline-test-jwt-secret-with-32-plus-characters','FIELD_ENCRYPTION_KEY':'dGVzdC1vbmx5LWZpZWxkLWtleS0wMDAwMDAwMDAwMDA=','LIVE_TRADING_ENABLED':'false','MARKETDATA_DISTRIBUTION_APPROVED':'false','SMTP_PASSWORD':'never-print-this-private-password',**overrides}
    return subprocess.run([sys.executable,str(ROOT/'infrastructure/env/validation.py')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
def test_live_error_reports_activation_fields_without_inputs():
    result=run_validation(LIVE_TRADING_ENABLED='true',TRADING_ENABLED='false',LIVE_EXECUTION_REFERENCEi='private-unrecognized-reference')
    output=result.stdout+result.stderr
    assert result.returncode==1 and 'FAIL application configuration' in output
    assert 'LIVE_EXECUTION_REFERENCE' in output and 'LIVE_TICK_SIZE_MULTIPLIER' in output
    assert 'never-print' not in output and 'private-unrecognized-reference' not in output
    assert 'input_value' not in output and 'Traceback' not in output

def test_market_reference_failure_is_distinguished_from_core():
    result=run_validation(MARKETDATA_DISTRIBUTION_APPROVED='true',MARKETDATA_APPROVAL_REFERENCE='false')
    assert result.returncode==1
    assert 'PASS application configuration' in result.stdout
    assert 'FAIL market-data configuration' in result.stderr and 'MARKETDATA_APPROVAL_REFERENCE' in result.stderr
    assert 'never-print' not in result.stderr

def test_field_validation_does_not_echo_secret_or_unknown_input():
    result=run_validation(LIVE_TICK_SIZE_MULTIPLIER='sensitive-invalid-value')
    assert result.returncode==1 and 'LIVE_TICK_SIZE_MULTIPLIER' in result.stderr
    assert 'sensitive-invalid-value' not in result.stderr

def test_offline_configuration_validation_passes():
    result=run_validation()
    assert result.returncode==0,result.stderr
    assert 'PASS market-data configuration' in result.stdout
    assert 'Environment validation passed' in result.stdout

def test_dhan_missing_reference_names_only_the_missing_field():
    result=run_validation(DHAN_EXECUTION_ENABLED='true',DHAN_EXECUTION_REFERENCE='',DHAN_TICK_SIZE_MULTIPLIER='0.01',DHAN_STREAM_ENABLED='true')
    assert result.returncode==1 and 'DHAN_EXECUTION_REFERENCE is missing/invalid' in result.stderr
    assert 'configure_dhan_reference.sh' in result.stderr and 'PENDING' in result.stderr
    assert 'DHAN_TICK_SIZE_MULTIPLIER' not in result.stderr and 'never-print' not in result.stderr

def test_dhan_multiplier_and_stream_failures_are_specific():
    result=run_validation(DHAN_EXECUTION_ENABLED='true',DHAN_EXECUTION_REFERENCE='internal-review-case',DHAN_TICK_SIZE_MULTIPLIER='0',DHAN_STREAM_ENABLED='true')
    assert result.returncode==1 and 'DHAN_TICK_SIZE_MULTIPLIER must be greater than zero' in result.stderr
    result=run_validation(DHAN_EXECUTION_ENABLED='true',DHAN_EXECUTION_REFERENCE='internal-review-case',DHAN_TICK_SIZE_MULTIPLIER='0.01',DHAN_STREAM_ENABLED='false')
    assert result.returncode==1 and 'DHAN_STREAM_ENABLED must be true' in result.stderr

def test_pending_internal_case_passes_configuration_without_claiming_approval():
    result=run_validation(DHAN_EXECUTION_ENABLED='true',DHAN_EXECUTION_REFERENCE='GNK-DHAN-REVIEW-fixture',DHAN_TICK_SIZE_MULTIPLIER='0.01',DHAN_STREAM_ENABLED='true')
    assert result.returncode==0,result.stderr
