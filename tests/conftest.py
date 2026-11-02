import os
os.environ.setdefault('APP_ENV','testing')
os.environ.setdefault('JWT_SECRET','test-secret-for-integration-tests-1234567890')
os.environ.setdefault('FIELD_ENCRYPTION_KEY','dGVzdC1vbmx5LWZpZWxkLWtleS0wMDAwMDAwMDAwMDA=')
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('STARTUP_CONNECTIVITY_CHECK','false')
