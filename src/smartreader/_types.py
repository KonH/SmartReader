from typing import Callable

from .types.app_state import AppStateData
from .types.content import Content
from .types.values import StateValue

# success, error
Callback = Callable[[bool, str], None]

# success, error, result
StringCallback        = Callable[[bool, str, str], None]
ScoreCallback         = Callable[[bool, str, float], None]
ContentCallback       = Callable[[bool, str, Content], None]
ContentListCallback   = Callable[[bool, str, list[Content]], None]
StateValueCallback    = Callable[[bool, str, StateValue], None]
AllStateCallback      = Callable[[bool, str, dict[str, StateValue]], None]
AppStateCallback      = Callable[[bool, str, AppStateData], None]

# Called from TelegramUI when an inline vote button is pressed
LiveFeedbackHandler = Callable[[Content, bool], None]
