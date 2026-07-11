import toast from "react-hot-toast";

type DeleteAllToastProps = {
  confirmLabel?: string;
  description?: string;
  onConfirm: () => Promise<void>;
  title?: string;
  toastId: string;
};

export function DeleteAllToast({
  confirmLabel = "Hapus Semua",
  description = "Semua job dan file video di folder outputs akan dihapus.",
  onConfirm,
  title = "Hapus seluruh riwayat dan output?",
  toastId,
}: DeleteAllToastProps) {
  return (
    <div className="confirmToast">
      <div className="confirmToast-copy">
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <div className="confirmToast-actions">
        <button className="ghostButton" type="button" onClick={() => toast.dismiss(toastId)}>
          Batal
        </button>
        <button
          className="dangerButton"
          type="button"
          onClick={async () => {
            toast.dismiss(toastId);
            await onConfirm();
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}
