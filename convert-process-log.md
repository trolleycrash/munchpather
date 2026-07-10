# Process log: building the Foundry → Pathbuilder converter

Shadow document describing how the converter was developed and why. Companion to
`README.md` / `convert.py`.

## Data sources

1. A real Foundry PF2e actor export (a level-2 Halfling Summoner). The input
   format. The repository ships a synthetic stand-in at
   `tests/fixtures/sample_actor.json`; the real character sheet is not included.
2. A real Pathbuilder backup (`.pbex`) of a throwaway character, used only as a
   format reference and to pin output shape/types. The repository ships a
   synthetic stand-in at `tests/fixtures/sample.pbex` that encodes just the save
   schema; the real backup is not included.
3. The Pathbuilder web app JS bundle (`Pathbuilder2eWebRemastered108b.js`,
   3.9 MB, compiled Kotlin/JS). Source of the internal id tables. This is
   Pathbuilder's proprietary source and is not included in the repository.

## Investigation and key findings

1. `.pbex` is a JSON envelope: `saves` (webID → *stringified* character JSON),
   `saveIDs` (stringified metadata), and empty `portraits`/`customFiles`/`folders`.
2. The inner character save uses proprietary internal ids. By diffing the sample
   save against the Foundry actor:
   - Ability boosts are integer indices. Confirmed **STR=0…CHA=5** two ways: the
     sample Cleric's `classKeyAbility=4`=WIS, and a Halfling Summoner's level-1 boosts
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
4. Feat slot numbers approximate Pathbuilder's scheme using each feat's taken
   level (`system.level.taken`, falling back to `value`). Multiple feats can
   still collide on one slot (e.g. archetype feats Foundry only tags as
   `class`); collisions are reported rather than silently dropped.
5. Platinum is omitted when zero (the sample omits it); coins map gp/sp/cp
   directly.
6. Spells are mapped from spontaneous/prepared spellcasting entries only; focus
   spells are excluded because Pathbuilder ties them to feats. Verified against
   the real actor's repertoire but not against a fully-built Summoner export.

## Development approach (TDD)

Built test-first with `pytest`, red → green → refactor per helper, in this order:
ability index → money → normalization/lookup → feat/background resolution →
gear/containers → wrapper + end-to-end. The end-to-end test includes a shape
check asserting every key in a real sample save is present with the same type.

## Left for the user / future work

Per-level skill increases, trained-skill choices, and class special selections
are left empty: Foundry stores only final skill ranks (not which skill was
chosen or increased at which level), so these are not reliably derivable and a
guess would produce a wrong character on import. Spells are mapped best-effort
(repertoire only). The cleanest way to sharpen the remaining fields is to build
the *same* character fully in Pathbuilder, export it, add it as a fixture, and
diff against our output.
