#!/usr/bin/env python3
"""Read-only operator diagnostics. Does not import the application or log values."""
import sys

def main():
    try:
        from app.database.session import engine
        from app.security.authentication import cache
        from app.core.config import settings
        from app.core.lifespan import check_dependencies,StartupCheckError
    except Exception:
        print('Startup configuration/secret loading failed. Validate environment and mounted-secret readability; values suppressed.')
        return 1
    try:
        check_dependencies(engine,cache,production=settings.app_env=='production')
    except StartupCheckError as error:
        print(str(error))
        return 1
    print('Database connectivity, runtime-role policy and Redis checks passed.')
    return 0
if __name__=='__main__':sys.exit(main())
