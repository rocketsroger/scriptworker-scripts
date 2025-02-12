from pushapkscript.publish_config import _google_should_do_dry_run, get_publish_config

AURORA_CONFIG = {
    "override_channel_model": "choose_google_app_with_scope",
    "apps": {
        "aurora": {
            "package_names": ["org.mozilla.fennec_aurora"],
            "default_track": "beta",
            "certificate_alias": "aurora",
            "service_account": "aurora@service.account.com",
            "credentials_file": "aurora.p12",
        }
    },
}

FOCUS_CONFIG = {
    "override_channel_model": "single_google_app",
    "app": {
        "certificate_alias": "focus",
        "package_names": ["org.mozilla.focus"],
        "service_account": "focus@service.account.com",
        "credentials_file": "focus.p12",
    },
}

FENIX_CONFIG = {
    "apps": {
        "production": {
            "package_names": ["org.mozilla.fenix"],
            "certificate_alias": "fenix",
            "google": {"default_track": "internal", "service_account": "fenix@service.account.com", "credentials_file": "fenix.p12"},
        }
    }
}

ANY_STORE_CONFIG = {
    "apps": {
        "production": {
            "package_names": ["org.mozilla.flex"],
            "certificate_alias": "flex",
            "google": {"default_track": "internal", "service_account": "flex@service.account.com", "credentials_file": "flex.p12"},
        }
    }
}


def test_get_publish_config_fennec():
    assert get_publish_config(AURORA_CONFIG, {}, "aurora") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "aurora",
        "google_track": "beta",
        "google_rollout_percentage": None,
        "username": "aurora@service.account.com",
        "secret": "aurora.p12",
        "package_names": ["org.mozilla.fennec_aurora"],
    }


def test_get_publish_config_fennec_track_override():
    assert get_publish_config(AURORA_CONFIG, {"google_play_track": "internal_qa"}, "aurora") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "aurora",
        "google_track": "internal_qa",
        "google_rollout_percentage": None,
        "username": "aurora@service.account.com",
        "secret": "aurora.p12",
        "package_names": ["org.mozilla.fennec_aurora"],
    }


def test_get_publish_config_fennec_rollout():
    assert get_publish_config(AURORA_CONFIG, {"rollout_percentage": 10}, "aurora") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "aurora",
        "google_track": "beta",
        "google_rollout_percentage": 10,
        "username": "aurora@service.account.com",
        "secret": "aurora.p12",
        "package_names": ["org.mozilla.fennec_aurora"],
    }


def test_get_publish_config_focus():
    payload = {"channel": "beta"}
    assert get_publish_config(FOCUS_CONFIG, payload, "focus") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "focus",
        "google_track": "beta",
        "google_rollout_percentage": None,
        "username": "focus@service.account.com",
        "secret": "focus.p12",
        "package_names": ["org.mozilla.focus"],
    }


def test_get_publish_config_focus_rollout():
    payload = {"channel": "production", "rollout_percentage": 10}
    assert get_publish_config(FOCUS_CONFIG, payload, "focus") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "focus",
        "google_track": "production",
        "google_rollout_percentage": 10,
        "username": "focus@service.account.com",
        "secret": "focus.p12",
        "package_names": ["org.mozilla.focus"],
    }


def test_get_publish_config_fenix():
    payload = {"channel": "production"}
    assert get_publish_config(FENIX_CONFIG, payload, "fenix") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "fenix",
        "google_track": "internal",
        "google_rollout_percentage": None,
        "username": "fenix@service.account.com",
        "secret": "fenix.p12",
        "package_names": ["org.mozilla.fenix"],
    }


def test_get_publish_config_fenix_rollout():
    payload = {"channel": "production", "rollout_percentage": 10}
    assert get_publish_config(FENIX_CONFIG, payload, "fenix") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "fenix",
        "google_track": "internal",
        "google_rollout_percentage": 10,
        "username": "fenix@service.account.com",
        "secret": "fenix.p12",
        "package_names": ["org.mozilla.fenix"],
    }


def test_target_google():
    payload = {"channel": "production", "target_store": "google"}
    assert get_publish_config(ANY_STORE_CONFIG, payload, "flex") == {
        "target_store": "google",
        "dry_run": True,
        "certificate_alias": "flex",
        "google_track": "internal",
        "google_rollout_percentage": None,
        "username": "flex@service.account.com",
        "secret": "flex.p12",
        "package_names": ["org.mozilla.flex"],
    }


def test_google_should_do_dry_run():
    task_payload = {"commit": True}
    assert _google_should_do_dry_run(task_payload) is False

    task_payload = {"commit": False}
    assert _google_should_do_dry_run(task_payload) is True

    task_payload = {}
    assert _google_should_do_dry_run(task_payload) is True
