/* EditTransactionForm — the correction path behind every "Edit if wrong" affordance
   (design.md §7.2). PATCH /api/transactions/{id} per schema.md §4; the server keeps
   the original values alongside for the audit trail (the mock mirrors the visible
   outcome only — noted in client.ts). */

import { useState } from 'react';
import type { Transaction } from '../types/schema';
import { api } from '../api/client';
import { Button } from './Button';
import { T, useT } from '../i18n';

export interface EditTransactionFormProps {
  transaction: Transaction;
  onSaved: (t: Transaction) => void;
  onCancel: () => void;
}

export function EditTransactionForm({ transaction: t, onSaved, onCancel }: EditTransactionFormProps) {
  const { pick } = useT();
  const [amount, setAmount] = useState(String(t.amount_pkd));
  const [description, setDescription] = useState(t.description ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError(pick('Enter a positive amount', 'رقم درج کریں'));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const { data } = await api.patchTransaction(t.id, {
        amount_pkd: Math.round(parsed),
        description: description.trim() || null,
        // 'edited' per schema.md §1 statuses; server retains the original.
        status: 'edited',
      });
      onSaved(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-3 px-4 py-4"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <p className="text-sm font-semibold text-ink-black">
        <T en="Correct this entry" ur="اس انٹری میں ترمیم کریں" />
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-ink-black">
          <T en="Amount (PKR)" ur="رقم" />
          <input
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="min-h-touch rounded-button border border-rule-line bg-paper-raised px-3 font-numerals text-base text-ink-black"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-black">
          <T en="Note" ur="تفصیل" />
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="min-h-touch rounded-button border border-rule-line bg-paper-raised px-3 text-base text-ink-black"
          />
        </label>
      </div>
      {error && (
        <p role="alert" className="text-sm font-semibold text-ledger-red">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={saving}>
          <T en={saving ? 'Saving…' : 'Save correction'} ur={saving ? 'محفوظ ہو رہا ہے…' : 'محفوظ کریں'} />
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          <T en="Cancel" ur="محو کریں" />
        </Button>
      </div>
      <p className="text-xs text-ink-black opacity-75">
        <T
          en="The original values stay on record for the audit trail (schema.md §4 PATCH)."
          ur="اصل قیمتیں ریکارڈ میں محفوظ رہتی ہیں۔"
        />
      </p>
    </form>
  );
}
