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
from .gem_flow import gem_flow
from .cabbage_flow import cabbage_flow
from .equipment_enhancement_flow import equipment_enhancement_flow
from .back_from_chat_flow import back_from_chat_flow
from .elite_zombie_flow import elite_zombie_flow
from .afk_rewards_flow import afk_rewards_flow
from .union_gifts_flow import union_gifts_flow
from .hero_upgrade_arms_race_flow import hero_upgrade_arms_race_flow
from .stamina_claim_flow import stamina_claim_flow
from .stamina_use_flow import stamina_use_flow
from .soldier_training_flow import soldier_training_flow
from .soldier_upgrade_flow import soldier_upgrade_flow
from .rally_join_flow import rally_join_flow

__all__ = ['handshake_flow', 'treasure_map_flow', 'harvest_box_flow', 'corn_harvest_flow', 'gold_coin_flow', 'iron_bar_flow', 'gem_flow', 'cabbage_flow', 'equipment_enhancement_flow', 'back_from_chat_flow', 'elite_zombie_flow', 'afk_rewards_flow', 'union_gifts_flow', 'hero_upgrade_arms_race_flow', 'stamina_claim_flow', 'stamina_use_flow', 'soldier_training_flow', 'soldier_upgrade_flow', 'rally_join_flow']
