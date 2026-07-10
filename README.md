# Foundry VTT → Pathbuilder 2e converter

Converts a Foundry VTT PF2e **actor export** (`fvtt-Actor-*.json`) into a
Pathbuilder 2e **`.pbex` backup** that can be restored into the Pathbuilder app
(Menu → Backup / Restore). Foundry's PF2e system imports *from* Pathbuilder but
never exports back to it; this fills that gap.

## Usage

```bash
# Convert an actor (the reference tables in data/ are already committed).
python3 convert.py fvtt-Actor-YourCharacter.json -o character.pbex
```

The `data/` tables are checked in, so conversion works out of the box. To
regenerate them you need the Pathbuilder web app bundle
(`Pathbuilder2eWebRemastered108b.js`), which is not distributed here (it is
Pathbuilder's proprietary source); save it from your browser and run:

```bash
python3 extract_pathbuilder_tables.py path/to/Pathbuilder2eWebRemastered108b.js
```

Then in Pathbuilder: open the backup/restore screen and import `character.pbex`.

## How it works

Two stages keep the fragile bundle-parsing separate from the conversion logic.

1. `extract_pathbuilder_tables.py` harvests Pathbuilder's internal identifier
   strings (`PREFIX_Display Name`, e.g. `SUMMONER_Reinforce Eidolon`) from the
   compiled Pathbuilder app bundle and writes them to `data/`
   (`feats.json`, `backgrounds.json`, `index.json`). This is a *partial*
   catalogue: the bundle only embeds ids referenced in code, so it serves as a
   validation set for the ids the converter constructs.
2. `convert.py` reads the Foundry actor and builds the inner Pathbuilder save,
   then wraps it in the `.pbex` envelope (`saves`, `saveIDs`, `portraits`,
   `customFiles`, `folders`).

### Ability boost index

Pathbuilder stores boosts as integer indices in this fixed order:

| index | 0 | 1 | 2 | 3 | 4 | 5 |
|-------|-----|-----|-----|-----|-----|-----|
| ability | STR | DEX | CON | INT | WIS | CHA |

The same order is used for `classKeyAbility`, `getBackgroundBoostFreeSelection`,
`backgroundBoostLimitedSelection`, and `hashMapAncestryFreeBoostSelections`.

## What converts reliably

Character name, level, XP; age, gender, deity; ancestry / class labels; ability
boosts and key ability; ancestry free boost and background limited/free boost
selections; money (coins); languages; weapons, worn + stowed armour, equipment,
and containers; background (validated or constructed as `BACKGROUND_<name>`);
class/ancestry/skill feats (validated or constructed); notes (from biography).

## What converts best-effort

Spells (`hashMapPlayerSpells`) are mapped from the class repertoire/prepared
list, keyed `<Class>&<rank>&<index>` (cantrips at rank 0); focus spells are
excluded (Pathbuilder ties them to feats). Verify spell ranks after import.

## Known limitations (finish in the Pathbuilder app)

These are left empty because they are not reliably derivable from the Foundry
export (Foundry stores only final state, not the per-choice history Pathbuilder
needs):

1. Per-level skill increases and trained-skill choices (Foundry keeps only final
   skill ranks, not which skill was chosen at which level).
2. Class special selections (eidolon type, doctrine, divine font, etc.).
3. **Feat slot placement.** Feat *ids* are mapped, but Pathbuilder's exact slot
   names (`"Class Feat 4"`, etc.) are approximated from each feat's taken level;
   the converter reports every constructed id and any slot collisions so you can
   verify placement after import.

The converter prints a report of what matched the catalogue versus what was
constructed, so unmatched items are never hidden.

## Tests

```bash
python3 -m pytest
```

Synthetic fixtures live in `tests/fixtures/` (`sample_actor.json` and
`sample.pbex`, which encodes the Pathbuilder save schema). No real character
data is committed.

The suite includes an import-detail contract (`tests/test_contract.py`) that
validates the converter output against the real Pathbuilder format:

1. every emitted field is a known Pathbuilder save field, with a type matching
   what real exports use (`tests/fixtures/pbex_schema.json`);
2. the envelope is self-consistent (webID agreement across saves/saveIDs/inner,
   index level equals `characterLevel`);
3. value invariants hold (ability-boost indices 0..5, feat ids are `PREFIX_Name`,
   coins are non-negative ints);
4. cross-references resolve (`inContainerID` points at a real container).

`pbex_schema.json` is format metadata (field names and JSON types, no character
data). Regenerate it from your own exports with
`tools/generate_pbex_schema.py <export.pbex ...> --bundle pb.js`.
