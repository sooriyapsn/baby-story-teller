'use client';

import { type HTMLAttributes } from 'react';
import { Track } from 'livekit-client';
import { PhoneDisconnectIcon } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/livekit/button';
import { cn } from '@/lib/utils';
import { UseInputControlsProps, useInputControls } from './hooks/use-input-controls';
import { usePublishPermissions } from './hooks/use-publish-permissions';
import { TrackSelector } from './track-selector';

export interface ControlBarControls {
  leave?: boolean;
  microphone?: boolean;
}

export interface AgentControlBarProps extends UseInputControlsProps {
  controls?: ControlBarControls;
  isConnected?: boolean;
  onDeviceError?: (error: { source: Track.Source; error: Error }) => void;
}

/**
 * A control bar specifically designed for voice assistant interfaces
 */
export function AgentControlBar({
  controls,
  saveUserChoices = true,
  className,
  isConnected = false,
  onDisconnect,
  onDeviceError,
  ...props
}: AgentControlBarProps & HTMLAttributes<HTMLDivElement>) {
  const publishPermissions = usePublishPermissions();
  const {
    micTrackRef,
    microphoneToggle,
    handleAudioDeviceChange,
    handleMicrophoneDeviceSelectError,
  } = useInputControls({ onDeviceError, saveUserChoices });

  const visibleControls = {
    leave: controls?.leave ?? true,
    microphone: controls?.microphone ?? publishPermissions.microphone,
  };

  return (
    <div
      aria-label="Voice assistant controls"
      className={cn(
        'bg-background border-input/50 dark:border-muted flex flex-col rounded-[31px] border p-3 drop-shadow-md/3',
        className
      )}
      {...props}
    >
      <div className="flex gap-1">
        <div className="flex grow gap-1">
          {/* Toggle Microphone */}
          {visibleControls.microphone && (
            <TrackSelector
              kind="audioinput"
              aria-label="Toggle microphone"
              source={Track.Source.Microphone}
              pressed={microphoneToggle.enabled}
              disabled={microphoneToggle.pending}
              audioTrackRef={micTrackRef}
              onPressedChange={microphoneToggle.toggle}
              onMediaDeviceError={handleMicrophoneDeviceSelectError}
              onActiveDeviceChange={handleAudioDeviceChange}
            />
          )}
        </div>

        {/* Disconnect */}
        {visibleControls.leave && (
          <Button
            variant="destructive"
            onClick={onDisconnect}
            disabled={!isConnected}
            className="font-mono"
          >
            <PhoneDisconnectIcon weight="bold" />
            <span className="hidden md:inline">END CALL</span>
            <span className="inline md:hidden">END</span>
          </Button>
        )}
      </div>
    </div>
  );
}
