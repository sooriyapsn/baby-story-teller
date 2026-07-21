import { useLocalParticipantPermissions } from '@livekit/components-react';

// NOTE: avoids importing the protocol package as that leads to a significant bundle size increase
const MICROPHONE_PROTOCOL_SOURCE = 2;

export interface PublishPermissions {
  microphone: boolean;
}

export function usePublishPermissions(): PublishPermissions {
  const localPermissions = useLocalParticipantPermissions();

  const microphone =
    !!localPermissions?.canPublish &&
    (localPermissions.canPublishSources.length === 0 ||
      localPermissions.canPublishSources.includes(MICROPHONE_PROTOCOL_SOURCE));

  return { microphone };
}
