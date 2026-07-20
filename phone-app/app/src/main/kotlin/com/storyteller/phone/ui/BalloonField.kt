package com.storyteller.phone.ui

import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import kotlin.random.Random

/**
 * A native port of frontend/components/app/balloon-field.tsx: faint balloons
 * drifting up from the bottom of the screen and popping partway up, purely
 * ambient decoration behind the mascot.
 *
 * Driven by a manually-ticked wall-clock timer and plain math, not
 * Compose's `Animatable`/`animateTo` — see the comment on MascotCharacter
 * in Mascot.kt for why: those respect the OS "Animator duration scale"
 * setting and can go instant/frozen when it's off, which is not
 * acceptable for content a child is meant to actually see moving.
 */
private val BALLOON_COLORS = listOf(
    Color(0xFFFF8FA3),
    Color(0xFFFFD166),
    Color(0xFF8EC5FF),
    Color(0xFF7FD8BE),
    Color(0xFFC6A8FF),
    Color(0xFFFF9F6B),
)

private const val BALLOON_COUNT = 7

private data class BalloonConfig(
    val leftFraction: Float,
    val widthDp: Float,
    val color: Color,
    val riseSeconds: Float,
    val popAtFraction: Float,
    val phaseOffsetSeconds: Float,
)

private fun randomBalloonConfig(): BalloonConfig = BalloonConfig(
    leftFraction = 0.04f + Random.nextFloat() * 0.92f,
    widthDp = 36f + Random.nextFloat() * 30f,
    color = BALLOON_COLORS.random(),
    riseSeconds = 7f + Random.nextFloat() * 5f,
    popAtFraction = 0.25f + Random.nextFloat() * 0.55f,
    phaseOffsetSeconds = Random.nextFloat() * 6f,
)

@Composable
fun BalloonField(modifier: Modifier = Modifier) {
    var t by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        val start = withFrameNanos { it }
        while (true) {
            withFrameNanos { now -> t = (now - start) / 1_000_000_000f }
        }
    }

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val heightPx = constraints.maxHeight.toFloat()
        val widthPx = constraints.maxWidth.toFloat()
        repeat(BALLOON_COUNT) { index ->
            key(index) {
                val config = remember { randomBalloonConfig() }
                BalloonInstance(t = t, config = config, screenHeightPx = heightPx, screenWidthPx = widthPx)
            }
        }
    }
}

private const val POP_SECONDS = 0.25f

@Composable
private fun BalloonInstance(t: Float, config: BalloonConfig, screenHeightPx: Float, screenWidthPx: Float) {
    val cycleLength = config.riseSeconds + POP_SECONDS
    val phase = floorMod(t - config.phaseOffsetSeconds, cycleLength)

    val riseY: Float
    val popScale: Float
    val popAlpha: Float
    if (phase < config.riseSeconds) {
        val riseFraction = phase / config.riseSeconds
        riseY = -config.popAtFraction * screenHeightPx * riseFraction
        popScale = 1f
        popAlpha = (riseFraction / 0.15f).coerceAtMost(1f) * 0.35f
    } else {
        val popFraction = (phase - config.riseSeconds) / POP_SECONDS
        riseY = -config.popAtFraction * screenHeightPx
        popScale = 1f + popFraction * 0.4f
        popAlpha = 0.35f * (1f - popFraction)
    }

    val heightDp = config.widthDp * 1.2f
    Box(
        modifier = Modifier
            .graphicsLayer {
                translationX = config.leftFraction * screenWidthPx
                translationY = screenHeightPx + riseY
                scaleX = popScale
                scaleY = popScale
                alpha = popAlpha
            }
            .drawBehind {
                val w = config.widthDp
                val h = heightDp
                drawLine(
                    color = config.color.copy(alpha = 0.6f),
                    start = Offset(0f, -h * 0.05f),
                    end = Offset(0f, h * 0.25f),
                    strokeWidth = 1.5f,
                    cap = StrokeCap.Round,
                )
                drawCircle(color = config.color, radius = w * 0.06f, center = Offset(0f, -h * 0.08f))
                drawOval(
                    color = config.color,
                    topLeft = Offset(-w / 2f, -h - h * 0.1f),
                    size = Size(w, h),
                )
                drawOval(
                    color = Color.White.copy(alpha = 0.35f),
                    topLeft = Offset(-w * 0.28f, -h * 0.85f),
                    size = Size(w * 0.24f, h * 0.3f),
                )
            },
    ) {}
}

private fun floorMod(value: Float, modulus: Float): Float {
    val r = value % modulus
    return if (r < 0f) r + modulus else r
}
