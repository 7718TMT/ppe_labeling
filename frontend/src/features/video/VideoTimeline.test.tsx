import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { VideoTimeline } from './VideoTimeline';

describe('VideoTimeline',()=>{
  it('keeps human, threshold, and window layers distinct and selectable',()=>{
    const onSegment=vi.fn(),onSuggestion=vi.fn();
    render(<VideoTimeline frameCount={120} currentFrame={20} source="Threshold" selectedSegment="s1" onFrame={vi.fn()} onSegment={onSegment} onSuggestion={onSuggestion}
      segments={[{segment_id:'s1',track_id:1,start_frame:0,end_frame:20,label:'others',quality_status:'good',include_in_export:1,needs_review:0,source_type:'manual'}]}
      suggestions={[{suggestion_id:'g1',track_id:1,start_frame:30,end_frame:50,suggested_label:'falling',confidence:.9,review_status:'pending'}]}
      windows={[{window_id:'w1',track_id:1,start_frame:0,end_frame:59,label:'others',quality_status:'good',quality_score:.9,include_in_export:1}]}/>
    );
    fireEvent.click(screen.getByTitle('others 0-20'));
    fireEvent.click(screen.getByTitle('Threshold falling 90%'));
    expect(onSegment).toHaveBeenCalled();expect(onSuggestion).toHaveBeenCalled();
    expect(screen.getByTitle('others 0-20')).toHaveClass('ring-1');
    expect(screen.getByTitle('Threshold falling 90%')).toHaveClass('border-solid');
  });
});
