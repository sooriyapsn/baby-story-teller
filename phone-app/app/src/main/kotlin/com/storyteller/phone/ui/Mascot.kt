package com.storyteller.phone.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.graphicsLayer
import com.storyteller.phone.data.CharacterDef
import com.storyteller.phone.data.MascotAccessory
import com.storyteller.phone.voice.AgentState
import kotlin.math.min

/**
 * A native port of frontend/components/app/agent-character.tsx, drawn on a
 * Compose Canvas since there's no SVG/Lottie renderer here.
 *
 * Every gesture below is driven by a manually-ticked wall-clock timer
 * (`withFrameNanos`) and plain trigonometry — deliberately NOT Compose's
 * `animateFloat`/`infiniteRepeatable` APIs. Those respect the OS-level
 * "Animator duration scale" developer setting (a real accessibility
 * feature for motion-sensitive users, sometimes also dialed down by OEM
 * battery savers); when that's off, every Compose animation in every app
 * on the phone goes instant/frozen, which is exactly why the mascot looked
 * static on a test device even though the underlying agent-state detection
 * was working correctly. For this app the mascot's motion IS the content,
 * not decoration, so it can't be at the mercy of a system setting most
 * parents will never know exists — hand-rolling the timing here makes
 * every gesture immune to it, guaranteed to move on any phone.
 */
@Composable
fun MascotCharacter(
    characterDef: CharacterDef,
    agentState: AgentState,
    modifier: Modifier = Modifier,
) {
    var t by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        val start = withFrameNanos { it }
        while (true) {
            withFrameNanos { now -> t = (now - start) / 1_000_000_000f }
        }
    }

    val isSpeaking = agentState == AgentState.AGENT_SPEAKING
    val isThinking = agentState == AgentState.THINKING
    val isListening = agentState == AgentState.LISTENING
    val isConnecting = agentState == AgentState.CONNECTING
    val isOffline = agentState == AgentState.DISCONNECTED
    // Thinking overrides the grumpy fold too — everyone gets the same "hmm"
    // pose while the LLM is working, same as agent-character.tsx.
    val isGrumpyIdle = characterDef.grumpy && !isSpeaking && !isThinking && !isOffline

    val bobPeriod = if (isSpeaking) 0.9f else 2.4f
    val bob = if (isOffline) 0f else oscillate(t, bobPeriod, 0f, -24f)

    val thinkTilt = if (isThinking) oscillate(t, 0.9f, -3f, 3f) else 0f
    val blink = blinkScale(t)
    val eyeGlance = if (isThinking) oscillate(t, 0.8f, -3f, 3f) else 0f
    val mouthOpen = if (isSpeaking) oscillate(t, 0.34f, 0.3f, 0.85f) else 0.25f
    val dotBounce = if (isThinking) oscillate(t, 0.6f, 0f, -6f) else 0f

    // Speaking gestures big and lively; listening/connecting stays close to
    // still (just a faint breathing sway) so it visibly reads as "calm and
    // paying attention," not "still talking" — the two need to look
    // obviously different at a glance, not just share one animation style.
    val leftArmAngle = when {
        isOffline -> 0f
        isGrumpyIdle -> 34f
        isThinking -> -8f
        isSpeaking -> oscillate(t, 0.45f, -15f, 28f)
        else -> oscillate(t, 3.2f, -4f, 4f)
    }
    val rightArmAngle = when {
        isOffline -> 0f
        isGrumpyIdle -> -34f
        isThinking -> -132f
        isSpeaking -> oscillate(t, 0.45f, 15f, -28f)
        else -> oscillate(t, 3.2f, 4f, -4f)
    }

    val legPeriod = if (isSpeaking) 0.55f else if (isThinking) 2.0f else 3.2f
    val leftLegAngle = if (isOffline) 0f else oscillate(t, legPeriod, -14f, if (isSpeaking) 18f else -10f)
    val rightLegAngle = if (isOffline) 0f else oscillate(t, legPeriod, 14f, if (isSpeaking) -18f else 10f)

    val ring1 = 1f + ringPhase(t, 0f) * 0.65f
    val ring2 = 1f + ringPhase(t, 0.8f) * 0.65f

    Canvas(modifier = modifier.graphicsLayer(alpha = if (isOffline) 0.45f else 1f)) {
        val s = min(size.width, size.height) / 260f
        val offsetX = (size.width - 260f * s) / 2f
        val offsetY = (size.height - 260f * s) / 2f + bob * s

        translate(offsetX, offsetY) {
            scale(s, s, pivot = Offset.Zero) {
                // listening: big, bold pulsing radar rings — this is the
                // clearest signal she has that it's actually listening to
                // her right now, so it needs to read at a glance, not be a
                // subtle accent.
                if (isListening) {
                    drawCircle(
                        color = characterDef.accessoryColor,
                        radius = 82f * ring1,
                        center = Offset(100f, 108f),
                        alpha = (1f - (ring1 - 1f) / 0.65f).coerceIn(0f, 1f) * 0.9f,
                        style = Stroke(width = 7f),
                    )
                    drawCircle(
                        color = characterDef.accessoryColor,
                        radius = 82f * ring2,
                        center = Offset(100f, 108f),
                        alpha = (1f - (ring2 - 1f) / 0.65f).coerceIn(0f, 1f) * 0.9f,
                        style = Stroke(width = 7f),
                    )
                }

                // thinking: bouncing "..." thought trail, top-right
                if (isThinking) {
                    listOf(0, 1, 2).forEach { i ->
                        drawCircle(
                            color = characterDef.accessoryColor,
                            radius = 5f + i * 1.5f,
                            center = Offset(180f + i * 16f, 24f - i * 8f + dotBounce * (1f - i * 0.3f)),
                            alpha = 0.4f + i * 0.2f,
                        )
                    }
                }

                rotate(if (isThinking) thinkTilt else 0f, pivot = Offset(100f, 186f)) {
                    // accessory (star/bolt/heart) on a little stem
                    drawLine(
                        color = characterDef.bodyStroke,
                        start = Offset(100f, 40f),
                        end = Offset(100f, 20f),
                        strokeWidth = 4f,
                        cap = StrokeCap.Round,
                    )
                    drawAccessory(characterDef.accessory, characterDef.accessoryColor)

                    // ears
                    drawCircle(characterDef.ear, radius = 16f, center = Offset(48f, 70f))
                    drawCircle(characterDef.ear, radius = 16f, center = Offset(152f, 70f))

                    // head/body
                    drawCircle(characterDef.color, radius = 78f, center = Offset(100f, 108f))
                    drawCircle(
                        color = characterDef.bodyStroke,
                        radius = 78f,
                        center = Offset(100f, 108f),
                        style = Stroke(width = 3f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            colorStops = arrayOf(
                                0f to Color.White.copy(alpha = 0.55f),
                                0.35f to Color.White.copy(alpha = 0f),
                                1f to Color.Black.copy(alpha = 0.08f),
                            ),
                            center = Offset(70f, 75f),
                            radius = 130f,
                        ),
                        radius = 78f,
                        center = Offset(100f, 108f),
                    )

                    // arms
                    rotate(leftArmAngle, pivot = Offset(26f, 122f)) {
                        drawLine(
                            color = characterDef.color,
                            start = Offset(26f, 122f),
                            end = Offset(6f, 158f),
                            strokeWidth = 15f,
                            cap = StrokeCap.Round,
                        )
                        drawCircle(characterDef.color, radius = 11f, center = Offset(6f, 158f))
                    }
                    rotate(rightArmAngle, pivot = Offset(174f, 122f)) {
                        drawLine(
                            color = characterDef.color,
                            start = Offset(174f, 122f),
                            end = Offset(194f, 158f),
                            strokeWidth = 15f,
                            cap = StrokeCap.Round,
                        )
                        drawCircle(characterDef.color, radius = 11f, center = Offset(194f, 158f))
                    }

                    // legs
                    rotate(leftLegAngle, pivot = Offset(80f, 178f)) {
                        drawLine(
                            color = characterDef.color,
                            start = Offset(80f, 178f),
                            end = Offset(70f, 212f),
                            strokeWidth = 15f,
                            cap = StrokeCap.Round,
                        )
                        drawCircle(characterDef.color, radius = 11f, center = Offset(70f, 212f))
                    }
                    rotate(rightLegAngle, pivot = Offset(120f, 178f)) {
                        drawLine(
                            color = characterDef.color,
                            start = Offset(120f, 178f),
                            end = Offset(130f, 212f),
                            strokeWidth = 15f,
                            cap = StrokeCap.Round,
                        )
                        drawCircle(characterDef.color, radius = 11f, center = Offset(130f, 212f))
                    }

                    // cheeks
                    drawCircle(characterDef.cheek, radius = 12f, center = Offset(52f, 122f), alpha = 0.55f)
                    drawCircle(characterDef.cheek, radius = 12f, center = Offset(148f, 122f), alpha = 0.55f)

                    // grumpy brows
                    if (characterDef.grumpy) {
                        drawLine(
                            color = characterDef.mouth,
                            start = Offset(60f, 80f),
                            end = Offset(82f, 87f),
                            strokeWidth = 4f,
                            cap = StrokeCap.Round,
                        )
                        drawLine(
                            color = characterDef.mouth,
                            start = Offset(140f, 80f),
                            end = Offset(118f, 87f),
                            strokeWidth = 4f,
                            cap = StrokeCap.Round,
                        )
                    }

                    // eyes (blink by squashing the whole eye group vertically)
                    val eyeRadius = if (isListening) 12f else 10f
                    val glanceX = if (isThinking) eyeGlance else 0f
                    scale(1f, blink, pivot = Offset(100f, 98f)) {
                        drawCircle(Color.White, radius = eyeRadius, center = Offset(72f, 98f))
                        drawCircle(Color.White, radius = eyeRadius, center = Offset(128f, 98f))
                        drawCircle(
                            Color(0xFF3A2A18),
                            radius = 5.5f,
                            center = Offset(72f + glanceX, 98f - if (isThinking) 4f else 0f),
                        )
                        drawCircle(
                            Color(0xFF3A2A18),
                            radius = 5.5f,
                            center = Offset(128f + glanceX, 98f - if (isThinking) 4f else 0f),
                        )
                    }

                    // mouth
                    val mouthPath = Path()
                    when {
                        isSpeaking -> {
                            scale(1f, mouthOpen.coerceAtLeast(0.2f), pivot = Offset(100f, 140f)) {
                                drawOval(
                                    color = characterDef.mouth,
                                    topLeft = Offset(85f, 123f),
                                    size = Size(30f, 34f),
                                )
                            }
                        }
                        isThinking -> {
                            mouthPath.moveTo(86f, 141f)
                            mouthPath.quadraticTo(100f, 135f, 114f, 141f)
                            drawPath(
                                mouthPath,
                                color = characterDef.mouth,
                                style = Stroke(width = 4f, cap = StrokeCap.Round),
                            )
                        }
                        isConnecting -> {
                            drawLine(
                                color = characterDef.mouth,
                                start = Offset(90f, 138f),
                                end = Offset(110f, 138f),
                                strokeWidth = 4f,
                                cap = StrokeCap.Round,
                            )
                        }
                        characterDef.grumpy -> {
                            mouthPath.moveTo(84f, 138f)
                            mouthPath.quadraticTo(100f, 130f, 116f, 138f)
                            drawPath(
                                mouthPath,
                                color = characterDef.mouth,
                                style = Stroke(width = 4f, cap = StrokeCap.Round),
                            )
                        }
                        else -> {
                            mouthPath.moveTo(80f, 133f)
                            mouthPath.quadraticTo(100f, 152f, 120f, 133f)
                            drawPath(
                                mouthPath,
                                color = characterDef.mouth,
                                style = Stroke(width = 4f, cap = StrokeCap.Round),
                            )
                        }
                    }
                }
            }
        }
    }
}

/** Linear back-and-forth between [a] and [b] over [periodSeconds] — the hand-rolled equivalent of infiniteRepeatable(tween(...), RepeatMode.Reverse). */
private fun oscillate(t: Float, periodSeconds: Float, a: Float, b: Float): Float {
    val phase = floorMod(t, periodSeconds) / periodSeconds // 0..1
    val triangle = if (phase < 0.5f) phase * 2f else (1f - phase) * 2f // 0->1->0
    return a + (b - a) * triangle
}

/** 0 at the start of the period, ramping linearly to 1 — the equivalent of infiniteRepeatable(tween(...), RepeatMode.Restart), offset by [offsetSeconds] for staggered rings. */
private fun ringPhase(t: Float, offsetSeconds: Float): Float =
    floorMod(t - offsetSeconds, 1.6f) / 1.6f

/** Mostly-open eyes (scaleY 1) with a brief close every 4s, like a natural blink. */
private fun blinkScale(t: Float): Float {
    val phase = floorMod(t, 4f)
    return when {
        phase < 3.6f -> 1f
        phase < 3.76f -> 1f - (phase - 3.6f) / 0.16f * 0.92f
        else -> 0.08f + (phase - 3.76f) / 0.24f * 0.92f
    }
}

private fun floorMod(value: Float, modulus: Float): Float {
    val r = value % modulus
    return if (r < 0f) r + modulus else r
}

private fun DrawScope.drawAccessory(accessory: MascotAccessory, color: Color) {
    val path = Path()
    when (accessory) {
        MascotAccessory.HEART -> {
            path.moveTo(100f, 28f)
            path.cubicTo(94f, 20f, 82f, 20f, 82f, 32f)
            path.cubicTo(82f, 42f, 100f, 52f, 100f, 52f)
            path.cubicTo(100f, 52f, 118f, 42f, 118f, 32f)
            path.cubicTo(118f, 20f, 106f, 20f, 100f, 28f)
            path.close()
        }
        MascotAccessory.BOLT -> {
            path.moveTo(104f, 8f)
            path.lineTo(88f, 30f)
            path.lineTo(98f, 30f)
            path.lineTo(92f, 52f)
            path.lineTo(114f, 24f)
            path.lineTo(102f, 24f)
            path.close()
        }
        MascotAccessory.STAR -> {
            path.moveTo(100f, 8f)
            path.lineTo(104f, 16f)
            path.lineTo(113f, 16f)
            path.lineTo(106f, 22f)
            path.lineTo(108f, 31f)
            path.lineTo(100f, 25f)
            path.lineTo(92f, 31f)
            path.lineTo(94f, 22f)
            path.lineTo(87f, 16f)
            path.lineTo(96f, 16f)
            path.close()
        }
    }
    drawPath(path, color = color)
}
