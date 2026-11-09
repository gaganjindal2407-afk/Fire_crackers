Write a Python program using the pygame library that simulates a firework rocket. 
Please follow these requirements:

BEHAVIOR
Open a dark night-sky window (800x600) with a short instruction text: 
   "Press ENTER to launch a rocket".
2. Every time I press the ENTER key, a rocket launches from a random position 
   along the bottom of the screen.
3. The rocket rises upward with a small glowing trail behind it. 
   Add a "whoosh" or hissing sound while it ascends.
4. At a random height, the rocket explodes into many colorful particles 
   that spread outward in all directions, slow down, fall with gravity, 
   and slowly fade away.
5. Play a loud "boom" sound when it bursts.
6. Multiple rockets should be able to fly at the same time if I press ENTER 
   repeatedly.

VISUAL EFFECTS
Make the explosion look realistic with a glow effect (use additive blending 
  or semi-transparent circles).
Light up the sky briefly at the moment of explosion (a soft flash of the 
  explosion's color over the background).
Use random bright colors for each firework.

SOUND
Do NOT rely on external sound files. Generate the whoosh and boom sounds 
  in code using numpy (for example, filtered random noise with a decaying 
  volume), so the program works by running a single file.

CODE STYLE (very important)
Keep the code beginner-friendly and easy to understand.
Use simple classes: Rocket, Particle, and a main game loop.
Add clear comments above every section explaining what it does in plain 
  English.
Use meaningful variable names and put adjustable settings 
