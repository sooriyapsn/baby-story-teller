import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useVoiceAssistant } from '@livekit/components-react';
import { AgentCharacter, type CharacterId } from '@/components/app/agent-character';
import { cn } from '@/lib/utils';

const MotionContainer = motion.create('div');

const ANIMATION_TRANSITION = {
  type: 'spring',
  stiffness: 675,
  damping: 75,
  mass: 1,
};

// No camera/screen-share/chat in this app (voice-only), so the agent tile
// is always the only tile, always full-screen.
const AGENT_TILE_CLASSES = [
  'col-start-1 row-start-1',
  'col-span-2 row-span-3',
  'place-content-center',
];

interface TileLayoutProps {
  character: CharacterId;
}

export function TileLayout({ character }: TileLayoutProps) {
  const { state: agentState, audioTrack: agentAudioTrack } = useVoiceAssistant();

  return (
    <div className="pointer-events-none fixed inset-x-0 top-8 bottom-32 z-50 md:top-12 md:bottom-40">
      <div className="relative mx-auto h-full max-w-2xl px-4 md:px-0">
        <div className="grid h-full w-full grid-cols-[1fr_1fr] grid-rows-[90px_1fr_90px] place-content-center gap-x-2">
          <div className={cn('grid', AGENT_TILE_CLASSES)}>
            <AnimatePresence mode="popLayout">
              <MotionContainer
                key="agent"
                layoutId="agent"
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 5 }}
                transition={{ ...ANIMATION_TRANSITION, delay: 0.15 }}
                className="bg-background aspect-square h-[90px] rounded-md border border-transparent transition-[border,drop-shadow]"
              >
                <AgentCharacter
                  state={agentState}
                  audioTrack={agentAudioTrack}
                  character={character}
                />
              </MotionContainer>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
