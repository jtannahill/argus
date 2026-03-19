'use client';

import { useState } from 'react';

interface Props {
  startTime: Date;
  endTime: Date;
  currentTime: Date;
  onTimeChange: (time: Date) => void;
  isPlaying: boolean;
  onPlayPause: () => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
}

export default function TimelineScrubber({
  startTime, endTime, currentTime, onTimeChange, isPlaying, onPlayPause, speed, onSpeedChange,
}: Props) {
  const total = endTime.getTime() - startTime.getTime();
  const current = currentTime.getTime() - startTime.getTime();
  const progress = total > 0 ? (current / total) * 100 : 0;

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-gray-800/90 p-4 z-10">
      <div className="flex items-center gap-4">
        <button onClick={onPlayPause} className="text-white text-xl w-8">
          {isPlaying ? '⏸' : '▶'}
        </button>
        <input
          type="range"
          min={0}
          max={100}
          value={progress}
          onChange={(e) => {
            const pct = parseFloat(e.target.value) / 100;
            onTimeChange(new Date(startTime.getTime() + pct * total));
          }}
          className="flex-1"
        />
        <div className="flex gap-1">
          {[1, 5, 10].map((s) => (
            <button
              key={s}
              onClick={() => onSpeedChange(s)}
              className={`px-2 py-1 rounded text-xs ${speed === s ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
            >
              {s}x
            </button>
          ))}
        </div>
        <span className="text-white text-xs font-mono min-w-[140px]">
          {currentTime.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
