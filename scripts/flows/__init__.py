"""
Flows - Action handlers triggered by icon detection.

Each flow handles a specific icon detection event.
Flows are executed in separate threads to avoid blocking the daemon.
"""

from .handshake_flow import handshake_flow
from .treasure_map_flow import treasure_map_flow
from .harvest_box_flow import harvest_box_flow
from .corn_harvest_flow import corn_harvest_flow
from .gold_coin_flow import gold_coin_flow
from .iron_bar_flow import iron_bar_flow

__all__ = ['handshake_flow', 'treasure_map_flow', 'harvest_box_flow', 'corn_harvest_flow', 'gold_coin_flow', 'iron_bar_flow']
