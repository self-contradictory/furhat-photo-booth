# Experiment Design

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

## Social Reciprocity Furhat (Helping the Robot)

- Furhat invites people to help it learn something about human expressions.
- Example: “Hey! I’m learning how humans smile. Could you teach me your best smile?”
- Furhat does not detect or imitate the smile (see the note below).
- Furhat responds: “Wow! I think I got it! Thank you for teaching me! Let’s take a picture to celebrate!”
- Goal: Investigate whether helping a robot and experiencing social reciprocity creates stronger positive emotions and a sense of connection.

## Implementation notes

- The robot does not hold a conversation. In every condition it speaks scripted lines at four moments
  (idle, when a person comes close, when the photo is taken, after the photo). The exact lines and
  gestures are in `booth/conditions.json`.
- Participants start the photo themselves by pressing Space on the laptop.
- Smile imitation in the Social Reciprocity condition was dropped: the robot asks to be taught a smile
  and thanks the participant, but does not detect or copy their expression. This is a limitation to
  report.
- Conditions are switched by hand at the start of each break window, and every photo and survey is
  tagged with the active condition.
