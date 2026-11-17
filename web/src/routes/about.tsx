import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/about')({ component: About })

function About() {
  return (
    <article className="space-y-4 pt-4 leading-relaxed">
      <h1 className="text-2xl font-bold">About this study</h1>
      <p>
        The Furhat Photo Booth is part of a student research project in the ROBT 414 course on
        human-robot interaction. We study how the robot's behaviour affects whether people come
        over to it and how they feel about the interaction afterwards.
      </p>
      <h2 className="text-lg font-semibold">What we collect</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>The photo you take at the booth.</li>
        <li>Your survey answers. The survey does not ask for your name, email or student ID.</li>
        <li>
          A researcher near the booth counts how many people pass by and stop. These are tallies
          only; nobody is identified.
        </li>
      </ul>
      <h2 className="text-lg font-semibold">How we use it</h2>
      <p>
        Survey answers are analysed in aggregate for the course report. Photos are stored only so
        you can download yours. Researchers look at them only to check how many people were in
        each photo, and they are never published.
      </p>
      <p>
        Taking part is voluntary. You can skip the photo, or leave the survey at any time. If you
        want your photo or answers deleted, contact the research team at the booth or through the
        course instructor and tell us the code at the end of your photo link.
      </p>
    </article>
  )
}
