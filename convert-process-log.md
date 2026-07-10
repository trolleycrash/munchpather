# Process log: building the Foundry → Pathbuilder converter

Shadow document describing how the converter was developed and why. Companion to
`README.md` / `convert.py`.

## Data sources

1. `fvtt-Actor-merrit-ashwillow-oVDYiUS35IjAqalh.json`: a real Foundry PF2e
   actor export (level-2 Halfling Summoner). The input format.
2. `pathbuilderexport (1).pbex`: a real Pathbuilder backup of a different
   character ("Unpaste Toothtabs", a level-1 Elf Cleric). Used only as a format
   reference and to pin output shape/types.
3. The Pathbuilder web app JS bundle (`Pathbuilder2eWebRemastered108b.js`,
   3.9 MB, compiled Kotlin/JS). Source of the internal id tables. This is
   Pathbuilder's proprietary source and is not included in the repository.

## Investigation and key findings

1. `.pbex` is a JSON envelope: `saves` (webID → *stringified* character JSON),
   `saveIDs` (stringified metadata), and empty `portraits`/`customFiles`/`folders`.
2. The inner character save uses proprietary internal ids. By diffing the sample
   save against the Foundry actor:
   - Ability boosts are integer indices. Confirmed **STR=0…CHA=5** two ways: the
     sample Cleric's `classKeyAbility=4`=WIS, and Merrit's level-1 boosts
     `["int","dex","cha","con"]` correspond to `[3,1,5,2]`.
   - Ids follow `PREFIX_Display Name` (`SUMMONER_Reinforce Eidolon`,
     `GENERAL_Battle Medicine`, `BACKGROUND_Scout`).
   - Skill feats use the `GENERAL_` prefix, not a `SKILL_` prefix (verified:
     `GENERAL_Battle Medicine`, `GENERAL_Quick Identification`).
3. The Pathbuilder website is behind a Cloudflare bot challenge, so the bundle
   could not be scraped remotely; the user exported it from their browser instead.
4. The bundle is a **partial** catalogue: it embeds ~4000 ids referenced in code,
   but not the full game database (e.g. `Halfling Luck`, `Observant Halfling`,
   `Scholar of the Ancients` are absent). The full data set is loaded at runtime
   from elsewhere. This is why the converter constructs-then-validates ids and
   reports anything not found, rather than requiring a catalogue hit.

## Assumptions

1. Constructing `PREFIX_Display Name` from Foundry item names is Pathbuilder's
   expected id form even when the id is not in the extracted subset. **Unverified**
   until a real import test; this is the main risk.
2. Foundry item `_id` values can be reused verbatim as Pathbuilder container ids
   (`inContainerID` / `hashMapEquipmentContainers` keys). They are opaque strings,
   so this should be safe.
3. Worn armour = the armour item with `system.equipped.inSlot == true`; other
   armour items are carried, not worn.
4. Feat slot numbers approximate Pathbuilder's scheme using each feat's
   `system.level.value`. Foundry sometimes records a feat's minimum level rather
   than the level taken, so slot placement can be wrong and is flagged in the
   report. Left for a second pass after the first real import.
5. Platinum is omitted when zero (the sample omits it); coins map gp/sp/cp
   directly.

## Development approach (TDD)

Built test-first with `pytest`, red → green → refactor per helper, in this order:
ability index → money → normalization/lookup → feat/background resolution →
gear/containers → wrapper + end-to-end. The end-to-end test includes a shape
check asserting every key in a real sample save is present with the same type.

## Left for the user / future work

Spells, per-level skill increases, class special selections, and precise feat
slots are best-effort/empty. The cleanest way to sharpen these is to export the
*same* character from Pathbuilder, add it as a fixture, diff against our output,
and fold corrections back into the tables and tests.
