# Swing Animation

This is the animation for when the batter swings. A batter can be
in 3 different stances and can also bunt. There is a gap in the chores
between power and bunt animations.

Fun little discovery is that the reset animations (3,7) are only smooth
with straight hit. There is a visual chop when it resets to left/right

Bunts do not set a variable. Testing bunts and they always hit the ball no
matter when the bunt is started.

Power hits:
- set var[2] = 1 before frame 7
- set var[2] = 2 before frame 8
- set var[2] = 3 before frame 9
- set var[2] = 0 before frame 10

I do not know if this is consistent across players, but, it is consistent
across the 3 power animations. I think this is used for being able to hit
the ball. Direction of ball? Power on ball?

Animations:
- Animation 0 - batter stance left power
- Animation 1 - batter stance straight power
- Animation 2 - batter stance right power
- Animation 3 - after power hit
- Animation 4 - batter stance left bunt
- Animation 5 - batter stance straight bunt
- Animation 6 - batter stance right bunt
- Animation 7 - after bunt hit

