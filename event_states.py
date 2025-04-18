from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class EventCreationStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_duration = State()
    waiting_for_description = State()
    meet_link_choice = State()
    confirmation = State()

async def is_in_event_creation(state: FSMContext) -> bool:
    """Проверяет, находится ли пользователь в процессе создания события"""
    current_state = await state.get_state()
    return current_state is not None and current_state.startswith("EventCreationStates")