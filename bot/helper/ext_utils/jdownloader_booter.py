from aiofiles.os import (
    path,
    makedirs,
    listdir,
    rename
)
from aioshutil import rmtree
from json import dump
from random import randint
from asyncio import sleep, wait_for
from re import match

from bot import (
    config_dict,
    LOGGER,
    jd_lock,
    bot_name
)
from .bot_utils import (
    cmd_exec,
    new_task,
    retry_function
)
from myjd import MyJdApi
from myjd.exception import (
    MYJDException,
    MYJDAuthFailedException,
    MYJDEmailForbiddenException,
    MYJDEmailInvalidException,
    MYJDErrorEmailNotConfirmedException,
)


class JDownloader(MyJdApi):
    def __init__(self):
        super().__init__()
        self._username = ""
        self._password = ""
        self._device_name = ""
        self.error = "JDownloader Credentials not provided!"
        self.device = None
        self.set_app_key("zee")

    @new_task
    async def initiate(self):
        self.device = None
        async with jd_lock:
            is_connected = await self.jdconnect()
            if is_connected:
                await self.boot()
                await self.connectToDevice()

    @new_task
    async def boot(self):
        await cmd_exec([
            "pkill",
            "-9",
            "-f",
            "java"
        ])
        self.device = None
        self.error = "Connecting... Try agin after couple of seconds"
        self._device_name = f"{randint(0, 1000)}@{bot_name}"
        jdata = {
            "autoconnectenabledv2": True,
            "password": config_dict["JD_PASS"],
            "devicename": f"{self._device_name}",
            "email": config_dict["JD_EMAIL"],
        }
        await makedirs(
            "/JDownloader/cfg",
            exist_ok=True
        )
        with open(
            "/JDownloader/cfg/org.jdownloader.api.myjdownloader.MyJDownloaderSettings.json",
            "w",
        ) as sf:
            sf.truncate(0)
            dump(
                jdata,
                sf
            )
        if not await path.exists("/JDownloader/JDownloader.jar"):
            pattern = r"JDownloader\.jar\.backup.\d$"
            for filename in await listdir("/JDownloader"):
                if match(
                    pattern,
                    filename
                ):
                    await rename(
                        f"/JDownloader/{filename}",
                        "/JDownloader/JDownloader.jar"
                    )
                    break
            await rmtree("/JDownloader/update")
            await rmtree("/JDownloader/tmp")
        cmd = "java -Dsun.jnu.encoding=UTF-8 -Dfile.encoding=UTF-8 -Djava.awt.headless=true -jar /JDownloader/JDownloader.jar"
        (
            _,
            __,
            code
        ) = await cmd_exec(
            cmd,
            shell=True
        )
        if code != -9:
            await self.boot()

    async def jdconnect(self):
        if (
            not config_dict["JD_EMAIL"]
            or not config_dict["JD_PASS"]
        ):
            return False
        try:
            await self.connect(
                config_dict["JD_EMAIL"],
                config_dict["JD_PASS"]
            )
            return True
        except (
            MYJDAuthFailedException,
            MYJDEmailForbiddenException,
            MYJDEmailInvalidException,
            MYJDErrorEmailNotConfirmedException,
        ) as err:
            self.error = f"{err}".strip()
            LOGGER.info(f"Failed to connect with jdownloader! ERROR: {self.error}")
            self.device = None
            return False
        except MYJDException as e:
            self.error = f"{e}".strip()
            LOGGER.info(
                f"Failed to connect with jdownloader! Retrying... ERROR: {self.error}"
            )
            return await self.jdconnect()

    async def connectToDevice(self):
        self.error = "Connecting to device..."
        await sleep(0.5)
        while True:
            self.device = None
            if (
                not config_dict["JD_EMAIL"]
                or not config_dict["JD_PASS"]
            ):
                self.error = "JDownloader Credentials not provided!"
                await cmd_exec([
                    "pkill",
                    "-9",
                    "-f",
                    "java"
                ])
                return False
            try:
                await self.update_devices()
                if not (devices := self.list_devices()):
                    continue
                for device in devices:
                    if self._device_name == device["name"]:
                        self.device = self.get_device(f"{self._device_name}")
                        break
                else:
                    continue
            except:
                continue
            break
        await self.device.enable_direct_connection()
        self.error = ""
        LOGGER.info("JDownloader is ready to use!")
        return True

    async def check_jdownloader_state(self):
        try:
            await wait_for(retry_function(self.device.jd.version), timeout=10)
        except:
            is_connected = await self.jdconnect()
            if not is_connected:
                raise MYJDException(self.error)
            await self.boot()
            isDeviceConnected = await self.connectToDevice()
            if not isDeviceConnected:
                raise MYJDException(self.error)


jdownloader = JDownloader()
