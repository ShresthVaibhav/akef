# Stats

Neither Enka's API nor SKPORT sends the numbers from the in-game stat screen, only what's
equipped. akef works them out the same way enka.network does, from Enka's public game
tables:

- operator base stats at their level, promotion and potential, plus attribute talent nodes
- weapon base ATK at its level and every weapon skill at its level, where refine, breakthrough and
  matching essence points all raise the skill level
- every gear stat at its enhance level, including stats that share one enhance slot
- STR adding HP, WILL adding healing received, and the main and secondary attribute adding ATK
- the few operators whose talents change their stats in their own way

Flat stats round down at the end, percentages don't, same as the game.

## How they're checked

The tests hold 46 numbers copied from enka.network for four operators (HP, ATK, attributes, crit,
damage bonuses, Ult gain, healing). Every one matches exactly, and SKPORT builds give the same
numbers as Enka builds for the same operator.

## Fields

`strength`, `agility`, `intellect`, `will`, `hp`, `atk`, `defense`, `crit_rate`, `crit_dmg`,
`arts_intensity`, `treatment_bonus`, `treatment_received`, `ult_gain`, `stagger_dmg`,
`physical_dmg`, `heat_dmg`, `electric_dmg`, `cryo_dmg`, `nature_dmg`, `basic_attack_dmg`,
`battle_skill_dmg`, `combo_skill_dmg`, `ultimate_dmg`, plus `main_attribute` and `sub_attribute`
naming the operator's two key attributes.

Percent stats are fractions, `0.564` is 56.4%.
