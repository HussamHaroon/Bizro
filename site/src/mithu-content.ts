/* Mithu guide copy — rotating bubble tips + SFX-toggle labels.

   Standalone module on purpose: it imports NOTHING (not content.ts, not
   React) so the orchestrator can merge these strings into content.ts's
   `mithu` section and hand them to GuideMithu / SfxToggle as props.

   Language law (same triad as site-i18n.tsx):
     en    — pure English. Zero Urdu/Arabic-script characters, zero
             roman-Urdu loan words.
     mixed — the house voice: English copy with Urdu-script brand accents
             (a short Urdu fragment appended after " · ").
     ur    — full Urdu, rendered in Nastaliq by the site's ur-mode CSS.  */

export type Lang = "ur" | "en" | "mixed";

export interface MithuGuideCopy {
  /** Four rotating guide tips. Each bubble-open shows the next one, cycling. */
  tips: string[];
  /** aria-label for the speech-bubble container. */
  bubbleLabel: string;
  /** SfxToggle word label while sound is ON. */
  sfxOn: string;
  /** SfxToggle word label while sound is OFF. */
  sfxOff: string;
}

export const MITHU_GUIDE_COPY: Record<Lang, MithuGuideCopy> = {
  en: {
    tips: [
      "Send a voice note — I do the typing.",
      "Receipt photo? I'll read it.",
      "Every entry gets a stamp.",
      "Your ledger becomes credit history.",
    ],
    bubbleLabel: "Mithu's guide tip",
    sfxOn: "Sound on",
    sfxOff: "Sound off",
  },
  mixed: {
    tips: [
      "Send a voice note — I do the typing · بولنا آپ، لکھنا میں",
      "Receipt photo? I'll read it · رسید پڑھنا میرا کام",
      "Every entry gets a stamp · ہر اندراج پر مہر",
      "Your ledger becomes credit history · کھاتہ ہی ساکھ",
    ],
    bubbleLabel: "Mithu · مٹھو کا ٹپ",
    sfxOn: "Sound on · آواز چالو",
    sfxOff: "Sound off · آواز بند",
  },
  ur: {
    tips: [
      "وائس نوٹ بھیجیں — ٹائپنگ میرا کام",
      "رسید کی تصویر؟ میں پڑھ لوں گا",
      "ہر اندراج پر مہر لگتی ہے",
      "آپ کا کھاتہ ہی آپ کی کریڈٹ تاریخ ہے",
    ],
    bubbleLabel: "مٹھو کا ٹپ",
    sfxOn: "آواز چالو",
    sfxOff: "آواز بند",
  },
};
