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

    # 클래스 변수로 이동

    PADDLING_KEYS = ["d", "s", "a"]
    WATER_OUTPUT_KEYS = ["i", "j", "k", "l"]

    def __init__(
        self,
        end_position: int = END_POSITION,
        water_level_limit: int = WATER_LEVEL_LIMIT,
    ):
        self.end_position = end_position
        self.water_level_limit = water_level_limit
        
        self.position = 0
        self.water_level = 0
        self.is_overwhelmed = False
        self.is_done = False
        
        self.key_inputs = asyncio.Queue()
        self.game_commands = asyncio.Queue()
        
        self.tasks = []

    def _check_game_end_conditions(self):
        if self.is_overwhelmed:
            return True, "배가 침몰했습니다!"
        elif self.position >= self.end_position:
            return True, "목표 위치에 도달했습니다!"
        return False, None

    async def game_state_manager(self):
        """
        핵심! 모든 게임 상태 변경을 담당하는 중앙 관리자
        오직 이 태스크만이 position, water_level, is_overwhelmed, is_done을 직접 수정합니다
        """
        while not self.is_done:
            # 게임 종료 조건 체크 (오직 여기서만!)
            game_ended, end_message = self._check_game_end_conditions()
            if game_ended:
                logger.info(end_message)
                self.is_done = True
                break
                
            try:
                # 명령 큐에서 하나씩 꺼내서 처리
                command = await asyncio.wait_for(self.game_commands.get(), timeout=0.1)
                
                if command["action"] == "paddle":
                    # 노 젓기 처리
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
                
                elif command["action"] == "drain_water":
                    # 물 퍼내기 처리
                    logger.info("물 퍼내기 시작...")
                    drain_amount = random.randint(1, 3)
                    if self.water_level - drain_amount < 0:
                        drain_amount = self.water_level
                    self.water_level -= drain_amount
                    logger.info(f"현재 물 높이: {self.water_level} (퍼낸 물: {drain_amount})")
                
                elif command["action"] == "add_water":
                    # 물 차오르기 처리
                    amount = command.get("amount", 1)
                    logger.info("물이 차오릅니다...")
                    self.water_level += amount
                    logger.info(f"현재 물 높이: {self.water_level}")
                    
                    # 물 높이 체크도 여기서 함께 처리
                    if self.water_level >= self.water_level_limit:
                        logger.info("배가 침몰합니다!")
                        self.is_overwhelmed = True
                
            except asyncio.TimeoutError:
                # 명령이 없으면 잠시 대기하고 계속
                continue

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
        
        while not self.is_done:
            logger.info("물이 차오르는 중...")
            amount = random.randint(min_, max_)
            await self.game_commands.put({"action": "add_water", "amount": amount})
            
            await asyncio.sleep(interval)

    async def key_worker(self):
        paddling_set = set()
        water_output_set = set()
        
        while not self.is_done:
            try:
                key = await asyncio.wait_for(self.key_inputs.get(), timeout=0.1)
                
                if key in self.PADDLING_KEYS and key not in paddling_set:
                    paddling_set.add(key)
                    if paddling_set == set(self.PADDLING_KEYS):
                        await self.game_commands.put({"action": "paddle"})
                        paddling_set.clear()

                elif key in self.WATER_OUTPUT_KEYS and key not in water_output_set:
                    water_output_set.add(key)
                    if water_output_set == set(self.WATER_OUTPUT_KEYS):
                        await self.game_commands.put({"action": "drain_water"})
                        water_output_set.clear()
                        
            except asyncio.TimeoutError:
                continue

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
            while not self.is_done:
                await asyncio.sleep(0.1)
        finally:
            listener.stop()

    async def run(self):
        """모든 태스크를 시작합니다. 이제 game_state_manager가 추가되었습니다"""
        self.tasks.append(asyncio.create_task(self.game_state_manager()))
        self.tasks.append(asyncio.create_task(self.key_worker()))
        self.tasks.append(asyncio.create_task(self.key_listener()))
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