import unittest

from backend.app.api.routes.health import health_check
from backend.app.core.config import settings
from backend.app.main import create_app


class RuntimeHardeningTests(unittest.TestCase):
    def test_health_check_exposes_only_liveness(self) -> None:
        self.assertEqual(health_check(), {"status": "ok"})

    def test_api_documentation_is_available_outside_production(self) -> None:
        previous_app_env = settings.app_env
        try:
            settings.app_env = "development"
            route_paths = {
                route.path
                for route in create_app().routes
                if hasattr(route, "path")
            }
        finally:
            settings.app_env = previous_app_env

        self.assertIn("/docs", route_paths)
        self.assertIn("/redoc", route_paths)
        self.assertIn("/openapi.json", route_paths)

    def test_api_documentation_is_disabled_in_production(self) -> None:
        previous_app_env = settings.app_env
        try:
            settings.app_env = "  PRODUCTION  "
            route_paths = {
                route.path
                for route in create_app().routes
                if hasattr(route, "path")
            }
        finally:
            settings.app_env = previous_app_env

        self.assertNotIn("/docs", route_paths)
        self.assertNotIn("/redoc", route_paths)
        self.assertNotIn("/openapi.json", route_paths)


if __name__ == "__main__":
    unittest.main()
