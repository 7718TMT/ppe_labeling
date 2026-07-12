import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PropertiesPanel } from './PropertiesPanel';

function renderPanel(isApproved: boolean, onApprovalChange = vi.fn()) {
  render(
    <PropertiesPanel
      addClassIds={[0]}
      assignClassIds={[0]}
      classNames={{ 0: 'Person' }}
      drawingClass={null}
      isApproved={isApproved}
      labels={[]}
      onApprovalChange={onApprovalChange}
      onAutoLabelCurrent={vi.fn()}
      onDelete={vi.fn()}
      onReset={vi.fn()}
      onSelectedClassChange={vi.fn()}
      onToggleAddMode={vi.fn()}
      processingAction={null}
      selectedImage="sample.jpg"
      selectedIndices={[]}
    />,
  );
  return onApprovalChange;
}

describe('PropertiesPanel approval action', () => {
  it('approves an unapproved image', () => {
    const onApprovalChange = renderPanel(false);

    fireEvent.click(screen.getByRole('button', { name: 'Approve Current Image' }));

    expect(onApprovalChange).toHaveBeenCalledWith(true);
  });

  it('renders the red unapprove action for an approved image', () => {
    const onApprovalChange = renderPanel(true);
    const button = screen.getByRole('button', { name: 'Unapprove Current Image' });

    expect(button).toHaveStyle({
      backgroundColor: 'rgba(127, 29, 29, 0.2)',
      borderColor: '#ef4444',
      color: '#ef4444',
    });
    fireEvent.click(button);
    expect(onApprovalChange).toHaveBeenCalledWith(false);
  });
});
