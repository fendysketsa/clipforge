import { Check, Download, Link2, Loader2, SlidersHorizontal } from "lucide-react";

type WorkflowBarProps = {
  hasSource: boolean;
  isProcessing: boolean;
  hasResults: boolean;
};

const steps = [
  { label: "Pilih sumber", hint: "Link atau upload", icon: Link2 },
  { label: "Atur gaya", hint: "Durasi & caption", icon: SlidersHorizontal },
  { label: "Siap posting", hint: "Review & download", icon: Download },
];

export function WorkflowBar({ hasSource, isProcessing, hasResults }: WorkflowBarProps) {
  const currentStep = hasResults ? 3 : isProcessing ? 2 : hasSource ? 2 : 1;

  return (
    <section className="workflowBar" aria-label="Alur pembuatan klip">
      <div className="workflowHeading">
        <span className="workflowEyebrow">Alur cepat</span>
        <p>Tiga langkah dari video panjang sampai klip siap posting.</p>
      </div>
      <ol className={`workflowSteps workflowSteps--${hasResults ? "complete" : currentStep}`}>
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isComplete = stepNumber < currentStep || hasResults;
          const isCurrent = stepNumber === currentStep && !hasResults;
          const Icon = isComplete ? Check : isCurrent && isProcessing ? Loader2 : step.icon;

          return (
            <li
              className={`${isComplete ? "complete" : ""} ${isCurrent ? "current" : ""}`}
              key={step.label}
              aria-current={isCurrent ? "step" : undefined}
            >
              <span className="workflowDot">
                <Icon className={isCurrent && isProcessing ? "spin" : ""} size={16} />
              </span>
              <span className="workflowStepCopy">
                <strong>{step.label}</strong>
                <small>{step.hint}</small>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
