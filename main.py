import asyncio
import random
import logging
from typing import Annotated
from pynput import keyboard


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(funcName)s %(asctime)s - %(levelname)s - %(message)s"
)


END_POSITION = 20
WATER_LEVEL_LIMIT = 10


class Paddler:

    PADDLING_KEYS = ["d", "s", "a"]
    WATER_OUTPUT_KEYS = ["i", "j", "k", "l"]

    position = 0
    water_level = 0

    def __init__(
        self,
        end_position: int = END_POSITION,
        water_level_limit: int = WATER_LEVEL_LIMIT,
    ):
        self.end_position = end_position
        self.water_level_limit = water_level_limit
        self.key_inputs = asyncio.Queue()
        self.is_overwhelmed = False
        self.tasks = []

    async def check_done(self):
        if self.is_overwhelmed:
            logger.info("배가 침몰했습니다!")
            return True
        elif self.position >= self.end_position:
            logger.info("목표 위치에 도달했습니다!")
            return True
        return False

    async def _paddling(self):
        logger.info("노를 젓기 시작합니다!")
        before_position = self.position
        move = random.choice([-1, 0, 1, 2])
        if move < 0:
            logger.info("아앗.. 배가 뒤로가잖아!!")
        elif move == 0:
            logger.info("배가 움직이지 않아!")
        else:
            logger.info("계속 이렇게 가자!")
        self.position += move
        logger.info(
            f"이전 위치: {before_position}, 현재 위치: {self.position}, 목표 위치: {self.end_position}"
        )

    async def _drain_water(self):
        logger.info("물 퍼내기 시작...")
        drain_water = random.randint(1, 3)
        if self.water_level - drain_water < 0:
            drain_water = self.water_level
        self.water_level -= drain_water
        logger.info(f"현재 물 높이: {self.water_level} (퍼낸 물: {drain_water})")

    async def _add_water(self):
        logger.info("물이 차오릅니다...")
        self.water_level += 1
        logger.info(f"현재 물 높이: {self.water_level}")

    async def check_water_level(self):
        while True:
            if self.water_level >= self.water_level_limit:
                logger.info("배가 침몰합니다!")
                self.is_overwhelmed = True
                break
            if self.position >= self.end_position:
                break
            await asyncio.sleep(0)

    async def sink(
        self,
        interval: Annotated[int, "물이 차오르는 간격 (단위: 초)"] = 2,
        min_: Annotated[int, "물이 차오르는 최소량"] = 1,
        max_: Annotated[int, "물이 차오르는 최대량"] = 3,
    ):
        logger.info("배가 침몰하기 시작합니다...")
        if max_ <= min_:
            logger.warning(
                "최대 물 높이는 최소 물 높이보다 커야 합니다. 기본값을 사용합니다."
            )
            max_ = min_ + 1
        logger.info(f"물이 차오르는 간격: {interval}초, 최소량: {min_}, 최대량: {max_}")
        while True:
            logger.info("물이 차오르는 중...")
            await self._add_water()
            if await self.check_done():
                break
            await asyncio.sleep(interval)

    async def key_worker(self):
        paddling_set = set()
        water_output_set = set()
        while True:
            if await self.check_done():
                break
            try:
                key = self.key_inputs.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
                continue
            if key in self.PADDLING_KEYS and key not in paddling_set:
                paddling_set.add(key)
                if paddling_set == set(self.PADDLING_KEYS):
                    await self._paddling()
                    paddling_set.clear()

            elif key in self.WATER_OUTPUT_KEYS and key not in water_output_set:
                water_output_set.add(key)
                if water_output_set == set(self.WATER_OUTPUT_KEYS):
                    await self._drain_water()
                    water_output_set.clear()

    async def key_listener(self):
        def on_press(key):
            try:
                if (
                    hasattr(key, "char")
                    and key.char in self.PADDLING_KEYS + self.WATER_OUTPUT_KEYS
                ):
                    self.key_inputs.put_nowait(key.char)
            except AttributeError:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

        try:
            while not await self.check_done():
                await asyncio.sleep(0.1)
        finally:
            listener.stop()

    async def run(self):
        self.tasks.append(asyncio.create_task(self.key_worker()))
        self.tasks.append(asyncio.create_task(self.key_listener()))
        self.tasks.append(asyncio.create_task(self.check_water_level()))
        self.tasks.append(asyncio.create_task(self.sink()))

        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for task in self.tasks:
                if not task.done():
                    task.cancel()


async def main():
    paddler = Paddler()
    await paddler.run()


if __name__ == "__main__":
    asyncio.run(main())
