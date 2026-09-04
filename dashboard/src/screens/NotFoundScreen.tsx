/* NotFoundScreen — the SPA catch-all. Before this, an unknown path (a stale
   /transactions link, a typo) rendered an empty shell under the nav: the
   bottom tabs still glowed but the page said nothing — a dead end for the
   loan officer and an unexplainable blank in a demo. One honest card, in
   the same stamped-ledger voice as every other screen, with ONE way back
   to safety (§4.4: one primary action per screen). */

import { Link } from 'react-router-dom';
import { useT } from '../i18n';
import { Button } from '../components/Button';
import { ScreenHeader } from '../components/ScreenHeader';
import { IconReport } from '../components/icons';

export function NotFoundScreen() {
  const { pick } = useT();
  return (
    <div className="flex flex-col gap-7">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-ink-green" />}
        title={pick('Page not found', 'صفحہ نہیں ملا')}
        purpose={pick('Nothing here', 'یہاں کچھ نہیں')}
      />
      <section className="bizro-card px-5 py-6">
        <p className="text-lg font-semibold text-ink-line">
          {pick('This page does not exist.', 'یہ صفحہ موجود نہیں ہے۔')}
        </p>
        <p className="mt-2 text-sm text-ink-line opacity-80">
          {pick(
            'The link may be old or mistyped. Your ledger is where it always was.',
            'شاید لنک پرانا یا غلط ہو۔ آپ کا کھاتہ اسی جگہ محفوظ ہے۔',
          )}
        </p>
        <div className="mt-5">
          <Link to="/ledger">
            <Button>{pick('Back to the ledger', 'کھاتے پر واپس جائیں')}</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
