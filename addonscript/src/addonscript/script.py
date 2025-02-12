import asyncio
import logging
import os

import aiohttp
import scriptworker.client
from aiohttp.client_exceptions import ClientError, ClientResponseError
from scriptworker.utils import retry_async

from addonscript.api import add_app_version, do_upload, do_create_version, get_signed_addon_info, get_signed_xpi, check_upload
from addonscript.exceptions import AMOConflictError, SignatureError
from addonscript.task import build_filelist
from addonscript.xpi import get_langpack_info

log = logging.getLogger(__name__)


def _craft_aiohttp_connector(context):
    return aiohttp.TCPConnector()


def get_default_config(base_dir=None):
    base_dir = base_dir or os.path.dirname(os.getcwd())
    default_config = {
        "work_dir": os.path.join(base_dir, "work_dir"),
        "artifact_dir": os.path.join(base_dir, "artifact_dir"),
        "schema_file": os.path.join(os.path.dirname(__file__), "data", "addonscript_task_schema.json"),
    }
    return default_config


async def sign_addon(context, locale):
    """Upload addons to AMO, then poll AMO for signed addons."""

    # upload langpack to AMO for validation/sanity check
    upload = await retry_async(do_upload, args=(context, locale), retry_exceptions=tuple([ClientError, asyncio.TimeoutError]))
    await retry_async(
        check_upload,
        args=(context, upload["uuid"]),
        attempts=10,
        retry_exceptions=(ClientError, asyncio.TimeoutError, SignatureError),
    )

    # create version or addon for signing
    try:
        version = await retry_async(do_create_version, args=(context, locale, upload["uuid"]), retry_exceptions=tuple([ClientError, asyncio.TimeoutError]))
    except AMOConflictError as exc:
        log.info(exc.message)
        version = {"id": None}

    # poll AMO for the the URL that contains the signed langpack
    signed_addon_info = await retry_async(
        get_signed_addon_info,
        args=(context, locale, version["id"]),
        attempts=10,  # 10 attempts with default backoff yield around 10 minutes of time
        # Most addons will be signed in less than that.
        retry_exceptions=(ClientError, asyncio.TimeoutError, SignatureError),
    )

    # make the signed langpack available in task's artifacts for downstream beetmover
    destination = os.path.join(context.config["artifact_dir"], "public/build/", locale, "target.langpack.xpi")
    os.makedirs(os.path.dirname(destination))
    await retry_async(get_signed_xpi, args=(context, signed_addon_info, destination))


def build_locales_context(context):
    langpack_info = []
    for file_ in build_filelist(context):
        current_info = get_langpack_info(file_)
        langpack_info.append(current_info)
    context.locales = {
        locale_info["locale"]: locale_info
        for locale_info in langpack_info
    }


async def async_main(context):
    connector = _craft_aiohttp_connector(context)
    async with aiohttp.ClientSession(connector=connector) as session:
        context.session = session
        build_locales_context(context)

        # ensure the versions exists on AMO before proceeding with uploading langpacks
        # building a set here since the version is shared among all locales usually
        versions = {context.locales[locale]["min_version"] for locale in context.locales}
        for version in versions:
            await retry_async(add_app_version, args=(context, version), retry_exceptions=tuple([ClientResponseError]))

        tasks = []
        for locale in context.locales:
            tasks.append(asyncio.ensure_future(sign_addon(context, locale)))
        await asyncio.gather(*tasks)


def main(config_path=None):
    return scriptworker.client.sync_main(async_main, config_path=config_path, default_config=get_default_config())


__name__ == "__main__" and main()
