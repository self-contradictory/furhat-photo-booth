# Experiment Design

## Final design (3 × 2)

Six cases: a **main condition** crossed with a **photo action**.

| Main condition | What the robot does before the photo |
| --- | --- |
| Passive | No speech, neutral face, does not look at people |
| Inviting | “Hi there! Let's take a photo together!” |
| Inviting with compliment | “Hi there! I love your style! Let's take a photo together!” |

| Photo action | When the participant presses the photo button |
| --- | --- |
| Smile | Furhat says “Let's smile!” and smiles for the photo |
| Silly face | Furhat says “Let's make silly faces!” and makes a silly face for the photo |

- The main condition tests how likely people are to approach the robot (observer tally).
- The photo action tests how a plain versus a playful interaction changes how people rate it (survey).
- The invite phrases are said by hand from Furhat Studio on a second laptop. The booth laptop records
  which main condition and action are running, and every photo and survey is tagged with both.
- There are no automatic or repeating phrases.

The sections below are the original four-condition plan. Playful became the silly-face action.

## Passive Furhat (Baseline Condition)

- Furhat stays still with a neutral expression.
- A banner next to it says: “Take a photo with Furhat! 📸”
- Furhat does not initiate any conversation.
- Goal: Measure how many people approach and take a photo without active social interaction.

## Inviting Furhat (Basic Social Interaction)

- Furhat proactively invites people to take a picture.
- Example: “Hey there! Would you like to take a photo with me? Come on, let’s do it!”
- Furhat uses basic eye contact and friendly expressions.
- Goal: Examine whether proactive verbal invitations increase engagement and improve mood.

## Complimenting Furhat (Positive Reinforcement)

- Furhat invites people and gives them a friendly compliment.
- Example: “Hey! You bring such positive energy! I bet we’ll take an amazing photo together!”
- Furhat smiles and speaks enthusiastically.
- Goal: Investigate whether positive affirmations from a robot improve participants’ mood and perception of the interaction.

## Playful Furhat (Shared Playfulness)

- Furhat invites people to make funny faces together.
- Example: “Hey! Want to try something funny? Let’s make the silliest faces possible! Ready? 3, 2, 1!”
- Furhat makes exaggerated facial expressions for the photo.
- Goal: Explore whether shared playful activity increases enjoyment, laughter, and positive emotions.

## Social Reciprocity Furhat (Helping the Robot) (dropped)

> Not run in the study. It depends on the robot reading and copying the participant's smile, and the
> booth robot only speaks scripted lines without perceiving faces. Kept here for the report.


- Furhat invites people to help it learn something about human expressions.
- Example: “Hey! I’m learning how humans smile. Could you teach me your best smile?”
- When the person smiles, Furhat imitates their expression.
- Furhat responds: “Wow! I think I got it! Thank you for teaching me! Let’s take a picture to celebrate!”
- Goal: Investigate whether helping a robot and experiencing social reciprocity creates stronger positive emotions and a sense of connection.

## Implementation notes

- The design is 3 × 2 (see *Final design* above).
- The robot does not hold a conversation. Invite phrases come from Furhat Studio. The robot looks at
  people who come close (not in Passive), but detection never makes it speak. When someone presses the
  photo button it says the action's phrase and holds the action's face for the shutter. The exact lines
  and faces are in `booth/conditions.json`.
- Participants start the photo themselves with the button on the laptop screen (or Space), followed by
  a 10-second countdown. Furhat starts its photo face a few seconds before the shutter and holds it.
- The main condition and action are switched by hand from the booth laptop, and every photo and survey
  is tagged with both.
