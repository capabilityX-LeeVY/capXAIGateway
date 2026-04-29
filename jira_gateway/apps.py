import os
import sys
from django.apps import AppConfig


class JiraGatewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jira_gateway'

    def ready(self):
        """Start JIRA status scheduler inside Django process (single process queue)."""
        # Only enable when running the web server process
        enabled = os.environ.get("JIRA_SCHEDULER_ENABLED", "1") == "1"
        is_runserver = "runserver" in sys.argv
        is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
        
        # For runserver with autoreload, only run in the child process
        # For runserver with --noreload, RUN_MAIN won't be set, so allow startup
        # For gunicorn or other servers, run normally
        if is_runserver:
            # Django autoreload uses RUN_MAIN to mark the child process
            # If RUN_MAIN is not set but --noreload is used, we should still start
            run_main = os.environ.get("RUN_MAIN")
            has_noreload = "--noreload" in sys.argv
            if run_main == "false":
                # Explicitly parent process with autoreload - skip
                return
            # Allow if: RUN_MAIN=true (child) or --noreload (single process)
            if run_main != "true" and not has_noreload:
                return
        elif not is_gunicorn:
            return

        if not enabled:
            return

        try:
            from jira_gateway.jirajob.check_jira_status import get_jira_status_checker
            checker = get_jira_status_checker()
            # Scheduler starts in JiraStatusChecker.__init__
            if checker:
                import logging
                logger = logging.getLogger(__name__)
                logger.info("✅ JIRA scheduler started inside Django process")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Failed to start JIRA scheduler in Django: {e}")
