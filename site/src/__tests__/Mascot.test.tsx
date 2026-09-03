/* Mascot.test.tsx — the Mithu parrot (../Mascot).

   Covers:
     - <Mithu /> renders for EVERY mood in the component's MithuMood list.
     - each mood yields a DISTINCT serialized SVG (moods read through posture
       and props, per the design law — so the markup must actually differ).
     - <GuideMithu /> opens its bubble on a tap, shows a tip, closes on an
       outside tap, and cycles to the next tip on re-open.

   Pointer events are fired through @testing-library as the brief requires.
   GuideMithu opens on a NON-mouse pointerdown (the touch/pen path); the bubble
   tip <p> is always in the DOM, so open/closed is asserted via aria-expanded +
   the is-open class, and the visible tip via its text content. */

import { describe, it, expect, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { Mithu, GuideMithu, type MithuMood } from "../Mascot";

/* The component's full mood list (MithuMood). */
const MOODS: MithuMood[] = [
  "wave",
  "listening",
  "thinking",
  "success",
  "clarify",
  "sleep",
];

afterEach(cleanup);

function serializedMood(mood: MithuMood): string {
  const { container } = render(<Mithu mood={mood} />);
  const html = container.innerHTML;
  cleanup();
  return html;
}

describe("Mithu — rendering", () => {
  it('renders <Mithu mood="wave" /> without crashing', () => {
    const { container } = render(<Mithu mood="wave" />);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("renders without crashing for every mood in the mood list", () => {
    for (const mood of MOODS) {
      const { container } = render(<Mithu mood={mood} />);
      expect(
        container.querySelector("svg"),
        `mood "${mood}" should render an <svg>`,
      ).not.toBeNull();
      cleanup();
    }
  });

  it("produces distinct SVG output for each mood", () => {
    const outputs = MOODS.map(serializedMood);
    // six moods must serialize to six unique renders
    expect(new Set(outputs).size).toBe(MOODS.length);
  });
});

describe("GuideMithu — bubble open / close", () => {
  const TIPS = ["Tip one", "Tip two", "Tip three", "Tip four"];

  it("opens on a tap, shows the first tip, and closes on an outside tap", () => {
    const { container, getByRole } = render(
      <GuideMithu tips={TIPS} label="Mithu guide" bubbleLabel="Mithu tip" />,
    );
    const root = getByRole("button");
    expect(root.getAttribute("aria-expanded")).toBe("false");

    // open: a non-mouse pointerdown on the mascot toggles the bubble open
    fireEvent.pointerDown(root, { pointerType: "touch" });
    expect(root.getAttribute("aria-expanded")).toBe("true");
    expect(root.className).toContain("is-open");
    expect(container.querySelector(".mithu-bubble__tip")?.textContent).toBe(
      TIPS[0],
    );

    // close: a pointerdown landing outside the mascot root
    fireEvent.pointerDown(document.body, { pointerType: "touch" });
    expect(root.getAttribute("aria-expanded")).toBe("false");
    expect(root.className).not.toContain("is-open");
  });

  it("cycles to the next tip on each open", () => {
    const { container, getByRole } = render(
      <GuideMithu tips={TIPS} label="Mithu guide" bubbleLabel="Mithu tip" />,
    );
    const root = getByRole("button");
    const tipText = () => container.querySelector(".mithu-bubble__tip")?.textContent;

    fireEvent.pointerDown(root, { pointerType: "touch" }); // open #1
    expect(tipText()).toBe(TIPS[0]);
    fireEvent.pointerDown(document.body, { pointerType: "touch" }); // close

    fireEvent.pointerDown(root, { pointerType: "touch" }); // open #2
    expect(tipText()).toBe(TIPS[1]);
  });
});
