#!/usr/bin/env bash
# Command Center Studio Video Builder // Job rnd-842
# Preset: 9:16 (1080x1920)
# Script Words: 27

echo '[STUDIO] Rendering 3 Hidden Stripe Tricks to Halt Churn...'
ffmpeg -y -f lavfi -i color=c=0x08090B:s=1080x1920:d=12 -i speech_rnd-842.mp3 -vf "drawtext=text='3 Hidden Stripe Tricks to Halt Churn':fontcolor=#E9B44C:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest exports/3_hidden_stripe_tricks_to_halt_churn_9x16.mp4
echo '[STUDIO] Render finished: exports/3_hidden_stripe_tricks_to_halt_churn_9x16.mp4'
