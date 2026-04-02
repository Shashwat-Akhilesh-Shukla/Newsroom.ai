import asyncio
from src.utils.events import event_bus
from src.agents.base import BaseAgent
from src.state import NewsroomState

class MockAgent(BaseAgent):
    async def process(self, state: NewsroomState) -> NewsroomState:
        self.log_decision("Testing", "Because I can")
        return state

    def validate_input(self, state: NewsroomState) -> bool:
        return True

    def get_routing_decision(self, state: NewsroomState) -> str:
        return "END"

def listener(event):
    print(f"EVENT RECEIVED: {event}")

event_bus.subscribe(listener)

async def main():
    agent = MockAgent("mock", {})
    state = {"metadata": {}}
    await agent.execute(state)

if __name__ == "__main__":
    asyncio.run(main())
