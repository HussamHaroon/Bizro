/* Settings screen (D5-2, schema.md §8 ruling D4-2) — per-merchant account
   settings: language (ur / mixed / en) and numeral style (western 1-2-3 /
   urdu ۱-۲-۳), persisted server-side via GET/PUT /api/merchants/{id}/settings
   so they follow the merchant across browsers and devices.

   Saving actually switches the whole app: the saved row is written back into
   the language/numerals providers (i18n), which every screen already reads.
   localStorage remains the first-paint fallback (§8) — this screen is the
   write-through path.

   Pickers are BIG touch targets (≥52px), never a dropdown (low-literacy
   users; bizro-ui-design: visible choices beat hidden ones). Save = the one
   primary action: disabled while saving, stamped "Saved ✓" on success
   (the screen's one rotated sticker), inline error + editable values on
   failure — never alert(). */

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { getSettings, putSettings } from '../api/client';
import type { LanguageSetting, NumeralStyle } from '../types/schema';
import { Button } from '../components/Button';
import { ScreenHeader } from '../components/ScreenHeader';
import { IconLangEn, IconLangMixed, IconLangUr, IconSettings } from '../components/icons';
import { formatAmount } from '../lib/format';
import { T, useLang, useNumerals } from '../i18n';
import { useMerchant } from '../merchant';

interface Prefs {
  language: LanguageSetting;
  numeral_style: NumeralStyle;
}

const LANGUAGE_OPTIONS: {
  value: LanguageSetting;
  label: ReactNode;
  icon: typeof IconLangUr;
}[] = [
  { value: 'ur', label: <span className="bizro-urdu leading-none">اردو</span>, icon: IconLangUr },
  { value: 'mixed', label: <span>Mixed</span>, icon: IconLangMixed },
  { value: 'en', label: <span>English</span>, icon: IconLangEn },
];

const NUMERAL_OPTIONS: { value: NumeralStyle; en: string; ur: string; sample: string }[] = [
  { value: 'western', en: 'Western', ur: 'مغربی', sample: '1-2-3' },
  { value: 'urdu', en: 'Urdu', ur: 'اردو', sample: '۱-۲-۳' },
];

/** One big picker chip — the ledger FILTER grammar at ≥52px (D5-2): active =
    green-fill + paper text + hard-sm shadow; icon + word on every option. */
function PickerButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      disabled={disabled}
      className={`inline-flex min-h-[52px] items-center justify-center gap-2 rounded-chip border-[3px] px-3 text-base font-semibold transition-colors duration-200 ease-out disabled:cursor-not-allowed disabled:opacity-60 ${
        active
          ? 'border-ink-line bg-fill-green text-paper shadow-hard-sm'
          : 'border-ink-line bg-paper-raised text-ink-line hover:bg-paper'
      }`}
    >
      {children}
    </button>
  );
}

export function SettingsScreen() {
  const { merchants, merchantId } = useMerchant();
  const { mode, setMode } = useLang();
  const { numerals, setNumerals } = useNumerals();

  const [loaded, setLoaded] = useState(false);
  const [language, setLanguage] = useState<LanguageSetting>(mode);
  const [numeralStyle, setNumeralStyle] = useState<NumeralStyle>(numerals);
  const [baseline, setBaseline] = useState<Prefs | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // App-side prefs read inside the load effect WITHOUT re-triggering it (the
  // effect keys on merchant only — a top-bar language toggle mid-edit must
  // not wipe the user's unsaved choices).
  const appPrefsRef = useRef<Prefs>({ language: mode, numeral_style: numerals });
  appPrefsRef.current = { language: mode, numeral_style: numerals };

  // Load the merchant's row on every merchant switch (D3-2). A SAVED row
  // (updated_at set) is the truth and seeds the pickers — mirroring
  // useSettingsHydration in App.tsx. An absent row (null) or an unsaved one
  // (implied defaults, updated_at null) seeds from the local first-paint
  // prefs instead (localStorage, §8), so the screen reflects what the user
  // currently sees and their first save persists exactly that.
  useEffect(() => {
    let alive = true;
    setLoaded(false);
    setError(null);
    getSettings(merchantId).then((row) => {
      if (!alive) return;
      const seed: Prefs = !row || row.updated_at === null ? appPrefsRef.current : row;
      setLanguage(seed.language);
      setNumeralStyle(seed.numeral_style);
      setBaseline(seed);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, [merchantId]);

  const dirty =
    baseline !== null && (language !== baseline.language || numeralStyle !== baseline.numeral_style);

  function pickLanguage(value: LanguageSetting) {
    setLanguage(value);
    setSaved(false);
    setError(null);
  }

  function pickNumeralStyle(value: NumeralStyle) {
    setNumeralStyle(value);
    setSaved(false);
    setError(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const row = await putSettings(merchantId, { language, numeral_style: numeralStyle });
      setLanguage(row.language);
      setNumeralStyle(row.numeral_style);
      setBaseline({ language: row.language, numeral_style: row.numeral_style });
      // Saving actually switches the whole app (ticket D5-2): write the saved
      // row into the providers every screen already reads.
      setMode(row.language);
      setNumerals(row.numeral_style);
      setSaved(true);
    } catch (e) {
      setSaved(false);
      setError(e instanceof Error ? e.message : 'Could not save settings');
    } finally {
      setSaving(false);
    }
  }

  const merchantName = merchants.find((m) => m.id === merchantId)?.display_name;

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconSettings className="h-9 w-9 text-ink-green" />}
        title="Settings"
        titleUr="سیٹنگز"
        purpose="Your account choices"
        purposeUr="اکاؤنٹ کی ترجیحات"
      />

      <section className="bizro-card bizro-card-hover flex flex-col gap-6 px-5 py-5 sm:px-6 sm:py-6">
        <header className="flex flex-col gap-1">
          <h2 className="flex flex-wrap items-baseline gap-x-2">
            <T
              en="Account Settings"
              ur="اکاؤنٹ سیٹنگز"
              className="font-numerals text-[22px] font-semibold text-ink-line"
              urClassName="text-[22px] font-semibold text-ink-line"
            />
          </h2>
          <p className="text-sm text-ink-line opacity-80">
            <T
              en="Saved for this account — every device"
              ur="یہ سیٹنگ ہر ڈیوائس پر محفوظ رہے گی"
            />
            {merchantName ? <span className="font-semibold"> · {merchantName}</span> : null}
          </p>
        </header>

        {!loaded && (
          <p className="text-sm text-ink-line opacity-75">
            <T en="Reading settings…" ur="سیٹنگز پڑھی جا رہی ہیں" />
          </p>
        )}

        {/* -- Language ------------------------------------------------------- */}
        <fieldset className="flex flex-col gap-2.5" disabled={!loaded}>
          <legend className="mb-1 flex flex-wrap items-baseline gap-x-2 text-sm font-semibold text-ink-line">
            <T en="Language" ur="زبان" />
          </legend>
          <div className="grid grid-cols-3 gap-2.5">
            {LANGUAGE_OPTIONS.map(({ value, label, icon: Icon }) => (
              <PickerButton
                key={value}
                active={language === value}
                disabled={!loaded || saving}
                onClick={() => pickLanguage(value)}
              >
                <Icon className="h-6 w-6" />
                {label}
              </PickerButton>
            ))}
          </div>
          <p className="text-xs text-ink-line opacity-75">
            <T en="Applies to the whole app when saved" ur="محفوظ کرنے پر پوری ایپ پر لاگو ہوگی" />
          </p>
        </fieldset>

        {/* -- Numerals -------------------------------------------------------- */}
        <fieldset className="flex flex-col gap-2.5" disabled={!loaded}>
          <legend className="mb-1 flex flex-wrap items-baseline gap-x-2 text-sm font-semibold text-ink-line">
            <T en="Numerals" ur="ہندسے" />
          </legend>
          <div className="grid grid-cols-2 gap-2.5">
            {NUMERAL_OPTIONS.map(({ value, en, ur, sample }) => (
              <PickerButton
                key={value}
                active={numeralStyle === value}
                disabled={!loaded || saving}
                onClick={() => pickNumeralStyle(value)}
              >
                <T en={en} ur={ur} />
                <span className="font-numerals tracking-wide">{sample}</span>
              </PickerButton>
            ))}
          </div>
          {/* The sample makes the choice visibly real (§4.7): the picked
              style rendering an actual ledger amount. */}
          <p className="flex flex-wrap items-baseline gap-x-1.5 text-xs text-ink-line opacity-75">
            <T en="Preview" ur="جائزہ" />
            <span className="font-numerals text-sm font-semibold text-ink-line">
              {formatAmount(4500, numeralStyle)}
            </span>
          </p>
        </fieldset>

        {/* -- Save row: the one primary action --------------------------------- */}
        <div className="flex flex-col gap-3 border-t-2 border-ink-line pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={!loaded || saving || !dirty}
            >
              {saving ? (
                <T en="Saving…" ur="محفوظ ہو رہی ہے" />
              ) : (
                <T en="Save settings" ur="محفوظ کریں" />
              )}
            </Button>
            {/* Stamped confirmation — the screen's one rotated sticker (D4-1);
                stays until the values are touched again. */}
            {saved && !dirty && (
              <span role="status" className="bizro-stamp bizro-stamp-in text-sm text-ink-green">
                <T en="Saved ✓" ur="محفوظ ✓" />
              </span>
            )}
          </div>
          {error && (
            <p role="alert" className="text-sm font-semibold text-ledger-red">
              <T en="Could not save — try again." ur="محفوظ نہیں ہو سکیں — دوبارہ کوشش کریں۔" />{' '}
              <span className="font-normal opacity-80">{error}</span>
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
