'use client';

import React, { useEffect } from 'react';
import { motion } from 'motion/react';
import { useSessionContext, useSessionMessages } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import type { CharacterId } from '@/components/app/agent-character';
import { BalloonField } from '@/components/app/balloon-field';
import { PreConnectMessage } from '@/components/app/preconnect-message';
import { TileLayout } from '@/components/app/tile-layout';
import {
  AgentControlBar,
  type ControlBarControls,
} from '@/components/livekit/agent-control-bar/agent-control-bar';
import { toastAlert } from '@/components/livekit/alert-toast';
import { cn } from '@/lib/utils';

const MotionBottom = motion.create('div');

const BOTTOM_VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut',
  },
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

interface SessionViewProps {
  appConfig: AppConfig;
  character: CharacterId;
  timeLimitMinutes: number;
}

export const SessionView = ({
  appConfig,
  character,
  timeLimitMinutes,
  ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);

  // Parent-set play time limit: end the call gently instead of leaving it
  // open indefinitely. Client-side only — good enough for a home app where
  // the "adversary" is a 4-year-old, not someone trying to bypass it.
  useEffect(() => {
    if (!timeLimitMinutes || timeLimitMinutes <= 0) return;
    const timer = setTimeout(() => {
      toastAlert({
        title: 'Playtime is up!',
        description: "That's all the story time for now — see you again soon!",
      });
      session.end();
    }, timeLimitMinutes * 60_000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-arm if the limit itself changes
  }, [timeLimitMinutes]);

  const controls: ControlBarControls = {
    leave: true,
    microphone: true,
  };

  return (
    <section className="bg-background relative z-10 h-full w-full overflow-hidden" {...props}>
      <BalloonField />

      <TileLayout character={character} />

      {/* Bottom */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="fixed inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-4" />
        )}
        <div className="bg-background relative mx-auto max-w-2xl pb-3 md:pb-12">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar
            controls={controls}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onDeviceError={({ error }) => {
              toastAlert({
                title: 'Microphone unavailable',
                description:
                  error.name === 'NotAllowedError'
                    ? 'Microphone access is blocked for this page. Click the icon left of the address bar, open Site settings, and set Microphone to Allow, then reload.'
                    : error.message,
              });
            }}
          />
        </div>
      </MotionBottom>
    </section>
  );
};
