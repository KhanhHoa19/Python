import React from 'react';
import { Modal } from './Modal.tsx';

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({ title, message, confirmLabel, danger, onConfirm, onCancel }) => (
  <Modal title={title} onClose={onCancel} width={440}>
    <p className="dialog-text">{message}</p>
    <div className="modal-actions">
      <button className="btn-secondary" onClick={onCancel}>Hủy</button>
      <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} autoFocus>{confirmLabel}</button>
    </div>
  </Modal>
);
