# Dungeon Survivor: The Last Lantern

## The promise

A 2D action adventure with crisp, hand-crafted pixel art, expressive character animation, and layered scenery. Each floor asks the player to clear its monsters, search for a chest containing the gate key, and make it through the gate. The dungeon grows more dangerous while the story gradually reveals why it opened.

The first game is a complete, focused dungeon journey. Its ending returns the hero to a living, brighter town. A sequel can then let players explore that town and the surrounding countryside at their own pace.

## Story

The town of **Larkspur** holds a Lantern Night festival every year. Families light paper lanterns and hang them along the streets to remember the people who kept the town safe long ago. The celebration ends with the ringing of the Dawn Bell, whose sound has protected Larkspur for generations.

On the night the game begins, the bell does not ring. The lanterns dim, a crack opens beneath the old bell tower, and creatures climb out of the buried halls below. The player character, **Neri**, is an apprentice mapmaker carrying a small, cracked lantern left by their missing grandmother, the last Bellkeeper.

Neri follows the light of that lantern into the dungeon. The first floors seem to be an abandoned fortress. Later, murals and echoes reveal that the Bellkeepers did not build it to imprison a monster: they built it to keep **the Hush**, a force that steals voices and makes people forget the bonds between them, from reaching the town. The old guardians are still trying to defend the bell, but the Hush has twisted them into enemies.

At the bottom, Neri finds the grandmother alive, holding the failing seal. The final enemy is the Hush wearing the shape of a great, many-voiced creature. Neri defeats it by surviving its attacks and restoring the Dawn Bell's three lost tones. The grandmother helps ring the bell; the dungeon's guardians become still, and the town's lights return.

### Opening sequence

1. **Title screen:** A torchlit dungeon room fills the screen. Neri stands in the foreground, a warrior enemy patrols behind them, and the cracked lantern flickers. The title and a clear **Start** button sit over the scene.
2. **Story prologue:** A short, illustrated sequence shows Lantern Night, the silent bell, and the dungeon opening. Text appears in a readable dialogue panel; the player can continue at their own pace and skip to play.
3. **First level:** Neri descends into the Root Cellars. A small tutorial introduces movement, attacking, enemies, the treasure chest, the key, and the locked gate.

### Ending and sequel handoff

After the final battle, Neri and the grandmother return to Larkspur at sunrise. The town begins in muted blue night colors; as neighbors recognize them and join the walk home, windows and lanterns light one by one. At the festival square, the townspeople ring their own handbells together. The screen blooms with warm colors, music, food stalls, dancing, and a quiet reunion between Neri and their grandmother.

The first game then gives the player a real ending and credits. After the credits, a map on Neri's wall shows a newly lit trail beyond Larkspur. This is a small invitation to the sequel, where the town itself can become an open world with relationships, rebuilding, festivals, and new mysteries.

## Level loop

Every level uses the same readable goals:

1. Explore the room or connected rooms and defeat every enemy.
2. Find the treasure chest. It contains the level's key.
3. Take the key to the gate. The gate opens only when Neri has the key and the level's enemies are defeated.
4. Enter the next floor, where enemy combinations, hazards, and layouts become more demanding.

The HUD should show health, enemies remaining, and key status. Interacting with a locked gate explains what is missing; opening a chest and unlocking a gate get distinct sound and visual cues. Keep a checkpoint at the start of each floor so a defeat is a setback, not a restart of the whole game.

## Enemy roster

- **Ironbound Warrior — melee:** Walks toward Neri, pauses for a visible wind-up, then swings. The player learns to step away and counterattack.
- **Ashweaver Mage — ranged:** Keeps distance and sends a slow, clearly telegraphed bolt across the room. The player learns to dodge sideways and close the gap.
- **Gloam Hound — fast attacker:** Circles briefly, then commits to a quick straight-line charge. Its recovery window rewards moving out of the way instead of trading hits.
- **The Hush — final boss:** A large, readable silhouette with three phases. It uses a ground wave, a slow tracking projectile, and summoned echoes. Every attack has a clear tell and a safe response; each phase ends with a damage window. Difficulty comes from combining learned patterns, not unavoidable damage.

## Five-floor campaign

| Floor | Place and visual identity | Challenge introduced |
| --- | --- | --- |
| 1 | Root Cellars: moss, old stone, warm torchlight | Warrior, basic chest and gate loop |
| 2 | Flooded Archive: blue water, shelves, reflections | Mage bolts and small water hazards |
| 3 | Emberworks: orange furnaces, moving sparks | Gloam Hound charges and mixed groups |
| 4 | Bellkeeper's Walk: faded banners and broken bells | All three enemy classes, longer rooms, first mini-boss |
| 5 | Quiet Chamber: pale stone, deep violet shadows, sound-reactive lights | The Hush boss and the restored-bell finale |

## 2D art direction

- Draw the dungeon as a top-down 2D environment with layered stone walls, floor tiles, arches, torches, chests, and gates.
- Use crisp pixel-art textures, cool blue-gray stone, warm lantern light, and violet-black shadows.
- Use animated character sprites with clear silhouettes and attack poses so the player can read movement and combat.
- Suggest depth with overlapping foreground details, highlights, shadows, and parallax layers while keeping the room and collisions easy to read.
- Polish one room first, then reuse its palette and visual rules across the campaign.

## Build order

1. **Title and opening:** pixel-art title screen, visible hero and enemy, mouse/keyboard Start, prologue panel, and skip/continue.
2. **Combat slice:** player attack, health, one warrior, one small room, hit feedback, and defeat/retry.
3. **Level objective:** enemy count, chest interaction, key pickup, locked gate, and a second room.
4. **Enemy classes:** add the mage and hound with distinct telegraphs and counters.
5. **Campaign:** build the five floor themes, checkpoints, boss phases, ending, and credits.
6. **Polish:** pixel-art sprites, sound, menus, accessibility settings, and the festival scene.

The current Pygame build includes the title and story sequence, a ten-room chest-key-gate run, Warrior/Mage/Zombie encounters, a telegraphed Ancient Guardian Commander fight, and victory, defeat, credits, and restart flows. The planned five distinct floor themes, Gloam Hound, and The Hush's multi-phase fight remain future work; the current final guardian is a smaller-scope campaign ending.

## Narrative references

These are references for broad craft ideas, not plots to reproduce:

- [Supergiant on Hades](https://www.supergiantgames.com/blog/hades-faq/): story and character relationships can continue advancing alongside dungeon progress.
- [Team Cherry on Hollow Knight](https://www.teamcherry.com.au/blog/introducing-hollow-knight): a forgotten underground kingdom can reveal its history through the places the player explores.
- [Children of Morta narrative design](https://blog.playstation.com/?p=217589): returning home can make dungeon journeys feel connected to relationships and a changing community.
