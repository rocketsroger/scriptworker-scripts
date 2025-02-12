import json
import tempfile

import pytest
from scriptworker.exceptions import TaskVerificationError

from beetmoverscript.constants import BUILDHUB_ARTIFACT, HASH_BLOCK_SIZE, INSTALLER_ARTIFACTS
from beetmoverscript.utils import (
    _check_locale_consistency,
    exists_or_endswith,
    extract_file_config_from_artifact_map,
    extract_full_artifact_map_path,
    generate_beetmover_manifest,
    generate_beetmover_template_args,
    get_addon_data,
    get_candidates_prefix,
    get_credentials,
    get_hash,
    get_partials_props,
    get_partner_candidates_prefix,
    get_partner_match,
    get_partner_releases_prefix,
    get_product_name,
    get_releases_prefix,
    get_url_prefix,
    is_partner_private_task,
    is_partner_public_task,
    is_promotion_action,
    is_release_action,
    matches_exclude,
    validated_task_id,
    write_file,
    write_json,
)

from . import get_fake_checksums_manifest, get_fake_valid_task, get_test_jinja_env


# get_hash {{{1
def test_get_hash():
    correct_sha1s = ("cb8aa4802996ac8de0436160e7bc0c79b600c222", "da39a3ee5e6b4b0d3255bfef95601890afd80709")
    text = b"Hello world from beetmoverscript!"

    with tempfile.NamedTemporaryFile(delete=True) as fp:
        # we generate a file by repeatedly appending the `text` to make sure we
        # overcome the HASH_BLOCK_SIZE chunk digest update line
        count = int(HASH_BLOCK_SIZE / len(text)) * 2
        for i in range(count):
            fp.write(text)
        sha1digest = get_hash(fp.name, hash_type="sha1")

    assert sha1digest in correct_sha1s


# write_json {{{1
def test_write_json():
    sample_data = get_fake_valid_task()["payload"]["releaseProperties"]

    with tempfile.NamedTemporaryFile(delete=True) as fp:
        write_json(fp.name, sample_data)

        with open(fp.name, "r") as fread:
            retrieved_data = json.load(fread)

        assert sample_data == retrieved_data


# write_file {{{1
def test_write_file():
    sample_data = "\n".join(get_fake_checksums_manifest())

    with tempfile.NamedTemporaryFile(delete=True) as fp:
        write_file(fp.name, sample_data)

        with open(fp.name, "r") as fread:
            retrieved_data = fread.read()

        assert sample_data == retrieved_data


# generate_beetmover_manifest {{{1
def test_generate_manifest(context, mocker):
    mocker.patch("beetmoverscript.utils.JINJA_ENV", get_test_jinja_env())
    manifest = generate_beetmover_manifest(context)
    mapping = manifest["mapping"]
    s3_keys = [mapping[m].get("target_info.txt", {}).get("s3_key") for m in mapping]
    assert sorted(mapping.keys()) == ["en-US", "multi"]
    assert sorted(s3_keys) == ["fake-99.0a1.en-US.target_info.txt", "fake-99.0a1.multi.target_info.txt"]

    expected_destinations = {
        "en-US": [
            "2016/09/2016-09-01-16-26-14-mozilla-central-fake/en-US/fake-99.0a1.en-US.target_info.txt",
            "latest-mozilla-central-fake/en-US/fake-99.0a1.en-US.target_info.txt",
        ],
        "multi": [
            "2016/09/2016-09-01-16-26-14-mozilla-central-fake/fake-99.0a1.multi.target_info.txt",
            "latest-mozilla-central-fake/fake-99.0a1.multi.target_info.txt",
        ],
    }

    actual_destinations = {k: mapping[k]["target_info.txt"]["destinations"] for k in sorted(mapping.keys())}

    assert expected_destinations == actual_destinations


# generate_beetmover_template_args {{{1
@pytest.mark.parametrize(
    "taskjson,partials",
    [
        ("task.json", {}),
        (
            "task_partials.json",
            {
                "target.partial-1.mar": {
                    "artifact_name": "target.partial-1.mar",
                    "buildid": "20170831150342",
                    "locale": "be",
                    "platform": "win32",
                    "previousBuildNumber": "1",
                    "previousVersion": "56.0.2",
                }
            },
        ),
    ],
)
def test_beetmover_template_args_generation(context, taskjson, partials):
    context.task = get_fake_valid_task(taskjson)
    expected_template_args = {
        "branch": "mozilla-central",
        "filename_platform": "android-arm",
        "product": "Fake",
        "stage_platform": "android-api-15",
        "platform": "android-api-15",
        "template_key": "fake_nightly",
        "upload_date": "2016/09/2016-09-01-16-26-14",
        "version": "99.0a1",
        "buildid": "20990205110000",
        "partials": partials,
        "locales": ["en-US"],
    }
    template_args = generate_beetmover_template_args(context)
    assert template_args == expected_template_args

    context.task["payload"]["locale"] = "en-US"
    context.task["payload"]["upstreamArtifacts"][0]["locale"] = "en-US"
    expected_template_args["template_key"] = "fake_nightly"
    expected_template_args["locales"] = ["en-US"]
    template_args = generate_beetmover_template_args(context)
    assert template_args == expected_template_args


@pytest.mark.parametrize(
    "payload, expected_locales",
    (
        ({"upstreamArtifacts": [{"path": "some/path", "taskId": "someTaskId", "type": "build"}]}, None),
        ({"upstreamArtifacts": [{"path": "some/path", "taskId": "someTaskId", "type": "build", "locale": "en-US"}]}, ["en-US"]),
        ({"locale": "en-US", "upstreamArtifacts": [{"path": "some/path", "taskId": "someTaskId", "type": "build", "locale": "en-US"}]}, ["en-US"]),
        ({"locale": "ro", "upstreamArtifacts": [{"path": "some/path", "taskId": "someTaskId", "type": "build", "locale": "ro"}]}, ["ro"]),
        (
            {
                "upstreamArtifacts": [
                    {"path": "some/path", "taskId": "someTaskId", "type": "build", "locale": "ro"},
                    {"path": "some/other/path", "taskId": "someOtherTaskId", "type": "signing", "locale": "ro"},
                    {"path": "some/path", "taskId": "someTaskId", "type": "build", "locale": "sk"},
                ]
            },
            ["ro", "sk"],
        ),
        ({"locale": "ro", "upstreamArtifacts": [{"path": "some/path", "taskId": "someTaskId", "type": "build"}]}, ["ro"]),
    ),
)
def test_beetmover_template_args_locales(context, payload, expected_locales):
    context.task = get_fake_valid_task("task_partials.json")
    payload["releaseProperties"] = context.task["payload"]["releaseProperties"]
    context.task["payload"] = payload
    context.task["payload"]["upload_date"] = "2018/04/2018-04-09-15-30-00"

    template_args = generate_beetmover_template_args(context)
    if expected_locales:
        assert "locale" not in template_args  # locale used to be the old way of filling locale
        assert template_args["locales"] == expected_locales
    else:
        assert "locale" not in template_args
        assert "locales" not in template_args


def test_beetmover_template_args_generation_release(context):
    context.resource = "dep"
    context.action = "push-to-candidates"
    context.task["payload"]["build_number"] = 3
    context.task["payload"]["version"] = "4.4"

    expected_template_args = {
        "branch": "mozilla-central",
        "product": "Fake",
        "filename_platform": "android-arm",
        "stage_platform": "android-api-15",
        "platform": "android-api-15",
        "template_key": "fake_candidates",
        "upload_date": "2016/09/2016-09-01-16-26-14",
        "version": "4.4",
        "buildid": "20990205110000",
        "partials": {},
        "build_number": 3,
        "locales": ["en-US"],
    }

    template_args = generate_beetmover_template_args(context)
    assert template_args == expected_template_args


@pytest.mark.parametrize(
    "locale_in_payload, locales_in_upstream_artifacts, raises",
    (("en-US", [], False), ("en-US", ["en-US"], False), ("ro", ["ro"], False), ("en-US", ["ro"], True), ("en-US", ["en-US", "ro"], True)),
)
def test_check_locale_consistency(locale_in_payload, locales_in_upstream_artifacts, raises):
    if raises:
        with pytest.raises(TaskVerificationError):
            _check_locale_consistency(locale_in_payload, locales_in_upstream_artifacts)
    else:
        _check_locale_consistency(locale_in_payload, locales_in_upstream_artifacts)


# is_release_action is_promotion_action {{{1
@pytest.mark.parametrize(
    "action,release,promotion", (("push-to-nightly", False, False), ("push-to-candidates", False, True), ("push-to-releases", True, False))
)
def test_is_action_release_or_promotion(action, release, promotion):
    assert is_release_action(action) is release
    assert is_promotion_action(action) is promotion


# get_partials_props {{{1
@pytest.mark.parametrize(
    "taskjson,expected",
    [
        ("task.json", {}),
        (
            "task_partials.json",
            {
                "target.partial-1.mar": {
                    "artifact_name": "target.partial-1.mar",
                    "buildid": "20170831150342",
                    "locale": "be",
                    "platform": "win32",
                    "previousBuildNumber": "1",
                    "previousVersion": "56.0.2",
                }
            },
        ),
    ],
)
def test_get_partials_props(taskjson, expected):
    partials_props = get_partials_props(get_fake_valid_task(taskjson))
    assert partials_props == expected


# get_candidates_prefix {{{1
@pytest.mark.parametrize(
    "product,version,build_number,expected",
    (("fennec", "bar", "baz", "pub/mobile/candidates/bar-candidates/buildbaz/"), ("mobile", "99.0a3", 14, "pub/mobile/candidates/99.0a3-candidates/build14/")),
)
def test_get_candidates_prefix(product, version, build_number, expected):
    assert get_candidates_prefix(product, version, build_number) == expected


# get_releases_prefix {{{1
@pytest.mark.parametrize("product,version,expected", (("firefox", "bar", "pub/firefox/releases/bar/"), ("fennec", "99.0a3", "pub/mobile/releases/99.0a3/")))
def test_get_releases_prefix(product, version, expected):
    assert get_releases_prefix(product, version) == expected


# get_partner_candidates_prefix {{{1
def test_get_partner_candidates_prefix():
    assert get_partner_candidates_prefix("foo/", "p1/s2") == "foo/partner-repacks/p1/s2/v1/"


# get_partner_releases_prefix {{{1
def test_get_partner_releases_prefix():
    expected = "pub/firefox/releases/partners/p1/s1/bar/"
    assert get_partner_releases_prefix("firefox", "bar", "p1/s1") == expected


# matches_exclude {{{1
@pytest.mark.parametrize("keyname,expected", (("blah.excludeme", True), ("foo/metoo/blah", True), ("mobile.zip", False)))
def test_matches_exclude(keyname, expected):
    excludes = [r"^.*.excludeme$", r"^.*/metoo/.*$"]
    assert matches_exclude(keyname, excludes) == expected


# get_partner_match {{{1
@pytest.mark.parametrize(
    "keyname,partners,expected",
    (
        ("blah.excludeme", [], None),
        ("foo/partner-repacks/p1/s1/v1/baz/biz.buzz", ["p1/s1"], "p1/s1"),
        ("foo/partner-repacks/p1/s1/v1/baz/biz.buzz", ["p1/s1", "p1/s2"], "p1/s1"),
        ("foo/partner-repacks/p1/s2/v1/baz/biz.buzz", ["p1/s1", "p1/s2"], "p1/s2"),
        ("foo/partner-repacks/p2/s3/v1/baz/biz.buzz", ["p1/s1", "p1/s2"], None),
    ),
)
def test_get_partner_match(keyname, partners, expected):
    assert get_partner_match(keyname, "foo/", partners) == expected


# product_name {{{1
@pytest.mark.parametrize(
    "appName,stage_platform,expected",
    (
        ("firefox", "dummy", "firefox"),
        ("firefox", "devedition", "devedition"),
        ("Firefox", "devedition", "Devedition"),
        ("Fennec", "dummy", "Fennec"),
        ("Firefox", "dummy", "Firefox"),
        ("fennec", "dummy", "fennec"),
    ),
)
def test_get_product_name(context, appName, stage_platform, expected):
    context.task["payload"]["releaseProperties"]["appName"] = appName
    context.task["payload"]["releaseProperties"]["platform"] = stage_platform
    assert get_product_name(context.task, context.config, lowercase_app_name=False) == expected


# is_partner_private_public_task {{{1
@pytest.mark.parametrize(
    "action,bucket,expected_private,expected_public",
    (
        ("push-to-dummy", "dep", False, False),
        ("push-to-dummy", "prod", False, False),
        ("push-to-partner", "dep-partner", True, False),
        ("push-to-partner", "dep", False, True),
    ),
)
def test_is_partner_private_public_task(context, action, bucket, expected_private, expected_public):
    context.action = action
    context.resource = bucket

    assert is_partner_private_task(context) == expected_private
    assert is_partner_public_task(context) == expected_public


# validated_task_id {{{1
@pytest.mark.parametrize("task_id", ("eSzfNqMZT_mSiQQXu8hyqg", "eSzfNqMZT_mSiQQXu8hyqg"))
def test_validated_task_id(task_id):
    assert validated_task_id(task_id) == task_id


# validated_task_id {{{1
@pytest.mark.parametrize("task_id", ("foobar", "", "eSzfNqMZT_mSiQQXu8hyq"))
def test_validated_task_id_raises(task_id):
    with pytest.raises(ValueError):
        validated_task_id(task_id)


def test_extract_file_config_from_artifact_map():
    task_def = get_fake_valid_task(taskjson="task_artifact_map.json")
    task_id = "eSzfNqMZT_mSiQQXu8hyqg"
    locale = "en-US"
    filename = "target.txt"
    expected = {
        "destinations": [
            "pub/mobile/nightly/2016/09/2016-09-01-16-26-14-mozilla-central-fake/en-US/fake-99.0a1.en-US.target.txt",
            "pub/mobile/nightly/latest-mozilla-central-fake/en-US/fake-99.0a1.en-US.target.txt",
        ],
        "checksums_path": "",
        "from_buildid": 19991231235959,
        "update_balrog_manifest": True,
    }
    assert extract_file_config_from_artifact_map(task_def["payload"]["artifactMap"], filename, task_id, locale) == expected


@pytest.mark.parametrize(
    "task_id, locale, filename",
    (
        ("wrongqMZT_mSiQQXu8hyqg", "en-US", "target.txt"),
        ("eSzfNqMZT_mSiQQXu8hyqg", "en-wrong", "target.txt"),
        ("eSzfNqMZT_mSiQQXu8hyqg", "en-US", "target.wrong"),
    ),
)
def test_extract_file_config_from_artifact_map_raises(task_id, locale, filename):
    task_def = get_fake_valid_task(taskjson="task_artifact_map.json")
    with pytest.raises(TaskVerificationError):
        extract_file_config_from_artifact_map(task_def["payload"]["artifactMap"], filename, task_id, locale)


@pytest.mark.parametrize(
    "path,locale,found", (("buildhub.json", "en-US", "buildhub.json"), ("buildhub.json", "en-GB", None), ("foobar", "en-GB", None), ("foobar", "en-US", None))
)
def test_extract_full_artifact_map_path(path, locale, found):
    task_def = get_fake_valid_task(taskjson="task_artifact_map.json")
    assert extract_full_artifact_map_path(task_def["payload"]["artifactMap"], path, locale) == found


@pytest.mark.parametrize(
    "filename, basenames, expected",
    (
        ("public/build/target.dmg", INSTALLER_ARTIFACTS, True),
        ("public/build/en-US/target.dmg", INSTALLER_ARTIFACTS, True),
        ("sfvxcvcxvbvcb", INSTALLER_ARTIFACTS, False),
        ("public/build/target.dmgx", INSTALLER_ARTIFACTS, False),
        ("target.dmg", INSTALLER_ARTIFACTS, True),
        ("target.dmgx", INSTALLER_ARTIFACTS, False),
        ("public/build/en-US/buildhub.json", BUILDHUB_ARTIFACT, True),
        ("public/build/buildhub.json", BUILDHUB_ARTIFACT, True),
        ("buildhub.json", BUILDHUB_ARTIFACT, True),
        ("public/build/buildhub.jsonxX", BUILDHUB_ARTIFACT, False),
        ("buildhub.jsonsdf03094", BUILDHUB_ARTIFACT, False),
        ("buildhub.jsonXXX", BUILDHUB_ARTIFACT, False),
    ),
)
def test_exists_or_endswith(filename, basenames, expected):
    assert exists_or_endswith(filename, basenames) == expected


@pytest.mark.parametrize(
    "cloud,bucket,expected,raises",
    (
        ("aws", "nightly", {"id": "dummy", "key": "dummy"}, False),
        ("gcloud", "nightly", "eyJoZWxsbyI6ICJ3b3JsZCJ9Cg==", False),
        ("gcloud", "fakeRelease", None, False),
        ("ibw", "fakeRelease", None, True),
    ),
)
def test_get_credentials(context, cloud, bucket, expected, raises):
    context.resource = bucket

    if raises:
        with pytest.raises(ValueError):
            get_credentials(context, cloud)
    else:
        aws_creds = get_credentials(context, cloud)
        assert aws_creds == expected


def test_get_url_prefix(context):
    assert get_url_prefix(context) == "https://archive.test"

    with pytest.raises(ValueError):
        context.resource = "FakeRelease"
        get_url_prefix(context)


def test_get_addon_data():
    addon_data = get_addon_data("tests/fixtures/dummy.xpi")
    assert addon_data["name"] == "@some-test-xpi"
    assert addon_data["version"] == "1.0.0"
