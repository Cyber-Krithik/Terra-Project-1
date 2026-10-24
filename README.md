# The Last Lantern

A 2D Pygame action adventure set beneath Larkspur. Neri follows a family lantern into an ancient dungeon after the town’s Dawn Bell falls silent.

## Run the game

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

In VS Code, select `.venv/bin/python` as the Python interpreter.

## Download the macOS build

Download the Apple silicon build from the [latest GitHub release](https://github.com/Cyber-Krithik/Terra-Project-1/releases/latest), unzip it, and open `The Last Lantern.app`. This build is for Apple silicon Macs only. Because it is not notarized, macOS may ask you to confirm before opening it; Control-click the app, choose **Open**, and confirm.

## Controls

- **WASD** or **arrow keys**: move.
- **Space**: attack.
- **Left Shift**: dash, with a short cooldown.
- **E**: open the chest or use the gate when nearby.
- **1**, **2**, or **3**: choose a chest upgrade.
- **Mouse click**: choose a chest upgrade from its card.
- **Enter**, **Space**, or a mouse click: advance the intro.
- **R**, **Enter**, or **Space**: restart after the Commander is defeated.
- **H**: return to the home page after the Commander is defeated.
- **Mouse click**: choose Restart Game or Back to Home on the victory page.
- **R**, **Enter**, or **Space**: restart after defeat.
- **Escape**: quit.

## Current game

The game has an eight-scene story intro, a ten-room dungeon run, warrior/mage/zombie encounters, a chest-key-gate objective on each room, and a final guardian encounter. Enemy groups grow and become tougher as Neri advances, with the current room and threat tier shown in the HUD. Elite warriors appear in rooms three, six, and nine. Each room chest offers three choices for one permanent-in-run upgrade to damage, health, or speed; choose with the number keys or mouse to claim the key. Defeating the Commander ends the run and opens a victory page where you can restart or return to the title screen.

The dungeon uses detailed stonework, torchlight, and lantern-lit objectives. An original, looping, synthesized dungeon score continues throughout play and changes to dedicated victory or defeat music for the endings. Enlarged character GIFs animate through movement, attacks, defeat, zombie revival, and the victory pose, with ground shadows, depth sorting, damage numbers, screen shake, dash feedback, invulnerability frames, enemy death particles, and readable enemy and boss health bars. The final encounter opens with a boss introduction and features a telegraphed triple-slam attack at low health. Synthesized sound effects accompany attacks, enemy hits and defeats, revival, slams, upgrades, and victory.

The game stays 2D. Depth and atmosphere will come from layered pixel-art scenery, careful lighting and color, and readable character sprites.
