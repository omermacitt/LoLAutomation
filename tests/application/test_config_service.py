"""Config persistence, including the shared-file guarantee that saves must not break."""

from __future__ import annotations

import json
import threading

from rune_pilot.application.config_service import ConfigConflict, ConfigService
from rune_pilot.domain.user_config import UserConfig
from rune_pilot.infrastructure.config_repository import ConfigRepository


def make_service(path: str) -> ConfigService:
    return ConfigService(ConfigRepository(path, fallback_paths=()))


def test_compare_and_write_is_atomic_between_two_settings_writers(config_path):
    service = make_service(config_path)
    revision = service.revision(service.load())
    barrier = threading.Barrier(2)
    outcomes = []

    def write(name):
        barrier.wait()
        try:
            outcomes.append(service.save(UserConfig(queue_name=name), expected_revision=revision))
        except ConfigConflict:
            outcomes.append("conflict")

    workers = [
        threading.Thread(target=write, args=(name,)) for name in ("Normal Draft", "Ranked Flex")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert outcomes.count(True) == 1
    assert outcomes.count("conflict") == 1


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestSave:
    def test_round_trip(self, config_path):
        service = make_service(config_path)
        service.save(UserConfig(queue_name="Ranked Flex", role_bans_ui={"TOP": 266}))

        loaded = service.load()
        assert loaded.queue_name == "Ranked Flex"
        assert loaded.role_bans_ui == {"TOP": 266}

    def test_missing_file_loads_defaults(self, config_path):
        assert make_service(config_path).load() == UserConfig()

    def test_unreadable_file_loads_defaults_instead_of_raising(self, config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        assert make_service(config_path).load() == UserConfig()

    def test_save_creates_missing_directories(self, tmp_path):
        nested = str(tmp_path / "a" / "b" / "user_config.json")
        assert make_service(nested).save(UserConfig(queue_name="Normal Draft"))
        assert read_json(nested)["queue_name"] == "Normal Draft"


class TestForeignKeysSurvive:
    """Removed accounts stay removed while independent preferences survive."""

    def test_settings_save_removes_obsolete_accounts(self, config_path):
        accounts = [{"id": "a1", "username": "tester", "encrypted_password": "x"}]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"accounts": accounts}, f)

        make_service(config_path).save(UserConfig(queue_name="Ranked Flex"))

        saved = read_json(config_path)
        assert "accounts" not in saved
        assert saved["queue_name"] == "Ranked Flex"

    def test_repository_cannot_reintroduce_accounts(self, config_path):
        repository = ConfigRepository(config_path, fallback_paths=())
        ConfigService(repository).save(UserConfig(queue_name="Ranked Flex"))

        repository.update(lambda data: data.__setitem__("accounts", [{"id": "a1"}]))

        saved = read_json(config_path)
        assert saved["queue_name"] == "Ranked Flex"
        assert "accounts" not in saved

    def test_concurrent_writers_do_not_lose_each_other(self, config_path):
        """
        Both owners write the file from their own threads — the UI thread saves
        settings while a login flow saves accounts. Neither may clobber the other.
        """
        repository = ConfigRepository(config_path, fallback_paths=())
        service = ConfigService(repository)
        barrier = threading.Barrier(2)

        def save_settings() -> None:
            barrier.wait()
            for i in range(50):
                service.save(UserConfig(queue_name=f"queue-{i}"))

        def save_preferences() -> None:
            barrier.wait()
            for i in range(50):
                repository.update(
                    lambda data, i=i: data.__setitem__("preferences", {"iteration": i})
                )

        threads = [
            threading.Thread(target=save_settings),
            threading.Thread(target=save_preferences),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        saved = read_json(config_path)
        assert saved["preferences"] == {"iteration": 49}
        assert saved["queue_name"] == "queue-49"


class TestRepository:
    def test_legacy_path_is_read_when_the_current_one_is_absent(self, tmp_path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text(json.dumps({"queue_name": "Ranked Flex"}), encoding="utf-8")

        current = str(tmp_path / "current.json")
        repository = ConfigRepository(current, fallback_paths=(str(legacy),))
        assert repository.read()["queue_name"] == "Ranked Flex"

    def test_saving_migrates_forward_to_the_current_path(self, tmp_path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text(json.dumps({"queue_name": "Ranked Flex"}), encoding="utf-8")

        current = str(tmp_path / "current.json")
        ConfigService(ConfigRepository(current, fallback_paths=(str(legacy),))).save(
            UserConfig(queue_name="Normal Draft")
        )

        assert read_json(current)["queue_name"] == "Normal Draft"

    def test_a_failing_mutation_leaves_the_file_untouched(self, config_path):
        repository = ConfigRepository(config_path, fallback_paths=())
        repository.update(lambda data: data.__setitem__("queue_name", "Ranked Flex"))

        def explode(data: dict) -> None:
            data["queue_name"] = "wrecked"
            raise RuntimeError("boom")

        assert repository.update(explode) is False
        assert read_json(config_path)["queue_name"] == "Ranked Flex"
