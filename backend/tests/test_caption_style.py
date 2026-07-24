from clipper import (
    AVAILABLE_FONTS,
    CaptionStyle,
    ClipCandidate,
    CodexEditPlan,
    ReactionCue,
    SoundEffectCue,
    TranscriptSegment,
    _hex_to_ass_color,
    apply_codex_audio_cues,
    apply_codex_structural_edit,
    build_candidate_pool,
    build_subtitle_style,
    candidate_fyp_analysis,
    candidate_story_metrics,
    caption_gradient_blur_filter,
    clip_topic_hashtags,
    codex_edit_plan,
    contextual_audio_mix_filter,
    contextual_sound_effect_cues,
    detect_visual_theme,
    detect_reaction_cues,
    emphasis_timestamps,
    enhanced_edit_filter,
    fallback_social_caption,
    ffmpeg_clean_metadata_args,
    hook_banner_text,
    is_source_branding_segment,
    landscape_caption_gradient_blur_filter,
    landscape_compilation_edit_filter,
    landscape_compilation_frame_filter,
    modern_blurred_video_frame_filter,
    modern_gradient_border_filters,
    pov_banner_text,
    remove_running_text_filter,
    resolve_codex_ideas,
    score_window,
    segments_for_clip,
    split_subtitle_text,
    visual_theme_profile,
)


def test_hex_to_ass_color_basic():
    # ASS uses &HAABBGGRR. White stays white, alpha 00.
    assert _hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    # Pure red -> BGR puts red last.
    assert _hex_to_ass_color("#FF0000") == "&H000000FF"
    # Pure blue -> blue first.
    assert _hex_to_ass_color("#0000FF") == "&H00FF0000"


def test_hex_to_ass_color_shorthand():
    assert _hex_to_ass_color("#FFF") == "&H00FFFFFF"


def test_hex_to_ass_color_invalid_falls_back():
    assert _hex_to_ass_color("nonsense") == "&H00FFFFFF"


def test_build_subtitle_style_upper_default():
    style = build_subtitle_style(CaptionStyle())
    assert "Alignment=6" in style
    assert "FontName=DejaVu Sans" in style
    assert "FontSize=10" in style
    assert "MarginL=36" in style
    assert "MarginR=36" in style
    assert "MarginV=70" in style
    assert "BackColour=&HC8000000" in style
    assert "BorderStyle=1" in style
    assert "Outline=1.5" in style
    assert "Shadow=0.35" in style
    assert "Blur=0.35" in style
    assert "WrapStyle=0" in style


def test_build_subtitle_style_center():
    style = build_subtitle_style(CaptionStyle(position="center"))
    assert "Alignment=10" in style
    assert "MarginV=0" in style


def test_build_subtitle_style_bottom():
    style = build_subtitle_style(CaptionStyle(position="bottom"))
    assert "Alignment=2" in style
    assert "MarginV=24" in style


def test_build_subtitle_style_font_whitelist():
    style = build_subtitle_style(CaptionStyle(font_family="Liberation Serif"))
    assert "FontName=Liberation Serif" in style
    # Unknown font falls back to default.
    bad = build_subtitle_style(CaptionStyle(font_family="Comic Sans; rm -rf"))
    assert "FontName=DejaVu Sans" in bad


def test_build_subtitle_style_outline_clamped():
    style = build_subtitle_style(CaptionStyle(outline_width=999))
    assert "Outline=8" in style
    style_zero = build_subtitle_style(CaptionStyle(outline_width=-5))
    assert "Outline=0" in style_zero


def test_build_subtitle_style_font_size_clamped():
    assert "FontSize=6" in build_subtitle_style(CaptionStyle(font_size=2))
    assert "FontSize=120" in build_subtitle_style(CaptionStyle(font_size=500))


def test_split_subtitle_text_keeps_default_lines_compact():
    chunks = split_subtitle_text("Di bagi kuahnya bagi tetangga supaya tidak melebar")
    assert chunks
    assert all(len(line) <= 24 for chunk in chunks for line in chunk.splitlines())
    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)


def test_available_fonts_has_defaults():
    assert "DejaVu Sans" in AVAILABLE_FONTS
    assert "Noto Sans" in AVAILABLE_FONTS


def test_caption_gradient_blur_filter_tracks_caption_position():
    upper = caption_gradient_blur_filter("upper")
    bottom = caption_gradient_blur_filter("bottom")

    assert "gblur=sigma=24" in upper
    assert "geq=" in upper
    assert "overlay=0:280" in upper
    assert "overlay=0:1450" in bottom


def test_running_text_cleanup_crops_bottom_and_preserves_vertical_aspect():
    value = remove_running_text_filter()

    assert value.startswith("crop=990:1760:45:0")
    assert "scale=1080:1920" in value
    assert "setsar=1" in value


def test_landscape_compilation_frame_is_full_hd_and_preserves_source_aspect():
    value = landscape_compilation_frame_filter("#FACC15", "#22D3EE")

    assert "crop=iw:trunc(ih*0.92/2)*2" in value
    assert "scale=1920:1080:force_original_aspect_ratio=increase" in value
    assert "scale=1840:1000:force_original_aspect_ratio=decrease" in value
    assert "[wide_canvas][wide_fg]overlay=(W-w)/2:(H-h)/2" in value


def test_landscape_compilation_edit_uses_chapters_and_sparse_emphasis():
    value = landscape_compilation_edit_filter(
        60,
        "part.hook.txt",
        section_number=2,
        section_count=5,
        emphasis_times=[12.0],
    )

    assert "text='POIN 02'" in value
    assert "text='BAGIAN 02 / 05'" in value
    assert "textfile='part.hook.txt'" in value
    assert "between(t,12.000" in value
    assert "y=1072" in value


def test_landscape_caption_blur_uses_16_by_9_canvas():
    value = landscape_caption_gradient_blur_filter("bottom")

    assert "crop=1920:250" in value
    assert "overlay=0:760" in value


def test_enhanced_edit_filter_adds_motion_hook_transition_and_progress():
    value = enhanced_edit_filter(60, "clip.hook.txt", pov_text_filename="clip.pov.txt")

    assert "scale=1120:1992" in value
    assert "vignette=PI/9" in value
    assert "fade=t=in" in value
    assert "textfile='clip.hook.txt'" in value
    assert "textfile='clip.pov.txt'" in value
    assert "text='POV'" in value
    assert "between(t,12.000,12.320)" in value
    assert "between(t,24.000,24.320)" in value
    assert "iw*t/60.000" in value
    assert "gblur=sigma=18" in value
    assert "[modern_bg][modern_fg]overlay=40:71" in value
    assert "#22D3EE@0.24" in value


def test_fyp_analysis_explains_hook_first_30_seconds_and_codex_ideas():
    segments = [
        TranscriptSegment(0, 3, "Tahukah kamu kenapa cara ini berbahaya?"),
        TranscriptSegment(3, 12, "Masalahnya ternyata ada pada keputusan pertama."),
        TranscriptSegment(12, 24, "Intinya ada satu kunci yang wajib diingat."),
        TranscriptSegment(24, 32, "Solusinya sederhana dan ini kesimpulannya."),
    ]

    analysis = candidate_fyp_analysis(segments, 32, 89)

    assert analysis["fyp_label"] == "Sangat kuat"
    assert "3 detik awal punya pemicu rasa penasaran" in analysis["strengths"]
    assert any("30 detik awal" in item for item in analysis["strengths"])
    assert analysis["pov"]
    assert analysis["improvement_ideas"]
    assert all(" — " in item for item in analysis["improvement_ideas"])


def test_codex_ideas_are_contextual_and_do_not_repeat_ending_fixes():
    segments = [
        TranscriptSegment(0, 8, "Nah jadi sebelumnya kita membahas hal lainnya."),
        TranscriptSegment(8, 18, "Masalah terbesar ternyata ada pada keputusan pertama."),
        TranscriptSegment(18, 28, "Kemudian pembahasannya masih berlanjut tanpa jawaban"),
    ]

    analysis = candidate_fyp_analysis(segments, 28, 58)
    ideas = analysis["improvement_ideas"]

    assert any(
        item.startswith("Hook —") and "Masalah terbesar ternyata" in item
        for item in ideas
    )
    assert sum(item.startswith("Ending —") for item in ideas) == 1
    assert not any(item.startswith("Loop —") for item in ideas)
    assert len(ideas) <= 3


def test_codex_structural_edit_trims_weak_intro_and_completes_ending():
    transcript = [
        TranscriptSegment(0, 4, "Nah jadi sebelumnya ada konteks panjang."),
        TranscriptSegment(4, 10, "Masalah terbesar ternyata ada pada keputusan pertama."),
        TranscriptSegment(10, 18, "Penjelasan ini masih berjalan tanpa penutup"),
        TranscriptSegment(18, 24, "Jawabannya akhirnya jelas dan bisa langsung diterapkan."),
    ]
    clip = ClipCandidate(
        1,
        0,
        18,
        18,
        62,
        "Keputusan Pertama",
        "test",
        " ".join(item.text for item in transcript[:3]),
        weaknesses=[
            "3 detik awal belum cukup menghentikan scroll",
            "payoff dan ending belum terasa tuntas",
        ],
        improvement_ideas=[
            "Hook — pindahkan potongan terkuat ke awal.",
            "Ending — lanjutkan sampai jawaban tuntas.",
        ],
    )

    apply_codex_structural_edit(
        clip,
        transcript,
        min_duration=10,
        max_duration=30,
    )

    assert 3.8 <= clip.start <= 4
    assert clip.end > 24
    assert any("Pembuka lemah dipangkas" in item for item in clip.applied_edits)
    assert any("Ending diperpanjang" in item for item in clip.applied_edits)
    assert clip.text.startswith("Masalah terbesar ternyata")
    assert clip.text.endswith("diterapkan.")


def test_codex_intro_trim_creates_room_for_payoff_without_exceeding_max_duration():
    transcript = [
        TranscriptSegment(0, 4, "Nah jadi sebelumnya ada konteks panjang."),
        TranscriptSegment(4, 10, "Masalah terbesar ternyata ada pada keputusan pertama."),
        TranscriptSegment(10, 20, "Penjelasan ini masih berjalan tanpa jawaban"),
        TranscriptSegment(20, 23.5, "Jawabannya jelas dan inilah kesimpulannya."),
    ]
    clip = ClipCandidate(
        1,
        0,
        20,
        20,
        62,
        "Keputusan Pertama",
        "test",
        " ".join(item.text for item in transcript[:3]),
        weaknesses=[
            "3 detik awal belum cukup menghentikan scroll",
            "payoff dan ending belum terasa tuntas",
        ],
        improvement_ideas=[
            "Hook — pindahkan klaim terkuat ke awal.",
            "Ending — lanjutkan sampai jawaban tuntas.",
        ],
    )

    apply_codex_structural_edit(
        clip,
        transcript,
        min_duration=10,
        max_duration=20,
    )

    assert clip.start >= 3.8
    assert clip.end >= 23.5
    assert clip.duration <= 20
    assert clip.text.endswith("kesimpulannya.")


def test_codex_render_plan_drives_hook_tempo_payoff_and_audio():
    clip = ClipCandidate(
        1,
        0,
        30,
        30,
        65,
        "Poin Utama",
        "test",
        "test",
        weaknesses=[
            "3 detik awal belum cukup menghentikan scroll",
            "tempo informasi awal berisiko terasa lambat",
            "payoff akhir belum terasa tegas",
        ],
    )
    plan = codex_edit_plan(clip)

    value = enhanced_edit_filter(
        30,
        "clip.hook.txt",
        payoff_text_filename="clip.payoff.txt",
        codex_plan=plan,
    )
    sounds = apply_codex_audio_cues([], 30, plan)

    assert plan.hook_boost and plan.tempo_boost and plan.ending_boost
    assert "between(t,0.05,0.58)" in value
    assert "between(t,7.000,7.320)" in value
    assert "text='INTI / PAYOFF'" in value
    assert "textfile='clip.payoff.txt'" in value
    assert [cue.trigger for cue in sounds] == ["hook Codex", "payoff Codex"]


def test_codex_render_plan_always_hooks_and_closes_with_a_seamless_loop():
    clip = ClipCandidate(
        1,
        0,
        30,
        30,
        90,
        "Hook Utama",
        "test",
        "Kenapa langkah ini penting? Jawabannya karena hasilnya berubah.",
        loop_score=65,
        boundary_quality="payoff_tuntas",
    )
    plan = codex_edit_plan(clip)

    value = enhanced_edit_filter(
        30,
        "clip.hook.txt",
        payoff_text_filename="clip.payoff.txt",
        codex_plan=plan,
    )
    sounds = apply_codex_audio_cues([], 30, plan)

    assert plan.hook_boost is True
    assert plan.loop_boost is True
    assert "MASIH INGAT INI?" not in value
    assert "between(t,29.720,29.970)" in value
    assert "fade=t=out" not in value
    assert [cue.kind for cue in sounds] == ["emphasis", "loop"]


def test_codex_render_plan_does_not_force_an_unrelated_loop():
    clip = ClipCandidate(
        1,
        0,
        30,
        30,
        78,
        "Penjelasan Umum",
        "test",
        "Pembahasan selesai tetapi tidak kembali ke pembuka.",
        loop_score=12,
        boundary_quality="kalimat_tuntas",
    )

    plan = codex_edit_plan(clip)
    sounds = apply_codex_audio_cues([], 30, plan)

    assert plan.loop_boost is False
    assert [cue.kind for cue in sounds] == ["emphasis"]


def test_codex_ideas_move_to_applied_feedback_after_render_treatments():
    ideas = [
        "Hook — pindahkan klaim terkuat ke detik 0.",
        "Alur — ringkas konteks sebelum konflik.",
        "Ending — jadikan pelajaran sebagai kalimat terakhir.",
        "Loop — kembalikan jawaban ke pertanyaan awal.",
        "Visual — beri emphasis pada poin utama.",
        "Audio — beri accent pada payoff.",
    ]

    remaining, applied = resolve_codex_ideas(
        ideas,
        CodexEditPlan(
            hook_boost=True,
            tempo_boost=True,
            ending_boost=True,
            loop_boost=False,
        ),
        enhanced_edit=True,
        output_format="vertical_short",
        drawtext_supported=True,
    )

    assert remaining == []
    assert len(applied) == 6
    assert any("tidak dipaksakan" in item for item in applied)


def test_codex_ideas_stay_manual_when_enhanced_edit_is_disabled():
    ideas = ["Ending — lanjutkan sampai payoff tuntas."]

    remaining, applied = resolve_codex_ideas(
        ideas,
        CodexEditPlan(ending_boost=True),
        enhanced_edit=False,
        output_format="vertical_short",
        drawtext_supported=True,
    )

    assert remaining == ideas
    assert applied == []


def test_story_metrics_reward_a_key_point_with_question_to_payoff_loop():
    strong = [
        TranscriptSegment(0, 4, "Kenapa keputusan pertama ini sangat penting?"),
        TranscriptSegment(4, 16, "Masalahnya satu kesalahan kecil membuat semua langkah berikutnya gagal."),
        TranscriptSegment(16, 26, "Jawabannya, periksa keputusan pertama agar hasilnya berhasil."),
    ]
    filler = [
        TranscriptSegment(0, 10, "Pada kesempatan kali ini kita akan membahas beberapa hal."),
        TranscriptSegment(10, 26, "Dan lain sebagainya masih akan dijelaskan pada bagian berikutnya"),
    ]

    strong_metrics = candidate_story_metrics(strong, 26)
    filler_metrics = candidate_story_metrics(filler, 26)

    assert strong_metrics["key_point_score"] > filler_metrics["key_point_score"]
    assert strong_metrics["loop_score"] >= 45
    assert strong_metrics["boundary_quality"] == "payoff_tuntas"


def test_candidate_pool_skips_arbitrary_mid_sentence_end():
    segments = [
        TranscriptSegment(0, 8, "Kenapa keputusan ini berbahaya?"),
        TranscriptSegment(8, 20, "Masalahnya terjadi ketika langkah pertama dibiarkan tanpa"),
        TranscriptSegment(20, 31, "Jawabannya adalah memeriksa risiko sampai hasilnya jelas."),
    ]

    candidates = build_candidate_pool(segments, min_duration=15, max_duration=40)

    assert candidates
    assert all(not (19.5 <= candidate.end <= 20.5) for candidate in candidates)
    assert any(candidate.boundary_quality == "payoff_tuntas" for candidate in candidates)


def test_ffmpeg_output_metadata_is_explicitly_sanitized():
    args = ffmpeg_clean_metadata_args()

    assert args[:4] == ["-map_metadata", "-1", "-map_chapters", "-1"]
    assert "license=" in args
    assert "copyright=" in args


def test_fyp_score_rewards_strong_opening_and_first_30_second_arc():
    strong = [
        TranscriptSegment(0, 3, "Tahukah kamu kenapa keputusan ini berbahaya?"),
        TranscriptSegment(3, 12, "Masalahnya ternyata bukan pada alat, tetapi langkah pertama."),
        TranscriptSegment(12, 22, "Intinya ada kunci penting yang wajib dipahami sebelum terlambat."),
        TranscriptSegment(22, 30, "Solusinya adalah memeriksa risiko lalu mengambil keputusan."),
        TranscriptSegment(30, 55, "Dengan cara itu masalah selesai dan hasilnya bisa dijelaskan dengan jelas."),
    ]
    weak = [
        TranscriptSegment(0, 12, "Nah jadi sebelumnya kita akan membahas beberapa hal terlebih dahulu."),
        TranscriptSegment(12, 28, "Kemudian ada bagian lain yang masih akan kita jelaskan nanti."),
        TranscriptSegment(28, 55, "Lalu pembicaraan berlanjut dengan konteks umum lainnya tanpa kesimpulan"),
    ]

    strong_score, _ = score_window(strong, 55)
    weak_score, _ = score_window(weak, 55)

    assert strong_score >= weak_score + 20


def test_pov_banner_is_compact_and_uses_candidate_angle():
    clip = ClipCandidate(
        1,
        0,
        60,
        60,
        85,
        "Judul",
        "test",
        "Isi",
        pov="POV: Kamu baru sadar keputusan kecil ini punya dampak yang sangat besar.",
    )

    value = pov_banner_text(clip)

    assert "POV:" not in value
    assert len(value.split()) <= 12


def test_modern_blurred_frame_keeps_sharp_inset_over_moving_background():
    value = modern_blurred_video_frame_filter("#22C55E", "#FACC15")

    assert "split=2[modern_bg_src][modern_fg_src]" in value
    assert "scale=360:640" in value
    assert "gblur=sigma=18" in value
    assert "scale=1000:1778" in value
    assert "#FACC15@0.24" in value
    assert "#22C55E@0.34" in value
    assert "overlay=40:71" in value


def test_modern_gradient_border_uses_dual_tone_glow_layers():
    filters = modern_gradient_border_filters("#22C55E", "#FACC15")
    value = ",".join(filters)

    assert "#22C55E@0.62" in value
    assert "#FACC15@0.20" in value
    assert "color=white@0.22" in value
    assert "x=35:y=66:w=505:h=7" in value


def test_enhanced_edit_filter_falls_back_without_drawtext():
    value = enhanced_edit_filter(
        60,
        "clip.hook.txt",
        emphasis_times=[10],
        show_text_overlays=False,
    )

    assert "drawtext=" not in value
    assert "textfile=" not in value
    assert "drawbox=x=30:y=61" in value
    assert "iw*t/60.000" in value


def test_mystery_islamic_theme_adds_context_badge_and_emphasis():
    clip = ClipCandidate(
        index=2,
        start=10,
        end=30,
        duration=20,
        score=95,
        title="Misteri Jin dan Hikmah Dalam Islam",
        reason="test",
        text="Ternyata tidak semua mitos boleh dipercaya menurut Islam.",
    )
    segments = [
        TranscriptSegment(10, 13, "Kisah ini bermula."),
        TranscriptSegment(15, 18, "Ternyata tidak semua mitos boleh dipercaya."),
        TranscriptSegment(22, 26, "Namun ada hikmah penting dalam Islam."),
    ]

    assert detect_visual_theme(clip) == "mystery"
    profile = visual_theme_profile(clip)
    assert profile["badge"] == "MISTERI / HIKMAH"
    times = emphasis_timestamps(clip, segments)
    assert times == [5, 12]

    value = enhanced_edit_filter(
        20,
        "clip.hook.txt",
        theme_profile=profile,
        emphasis_times=times,
        variation=1,
    )

    assert "scale=1140:2028" in value
    assert "MISTERI / HIKMAH" in value
    assert "CEK FAKTANYA" in value
    assert "between(t,5.000,5.420)" in value
    assert "#A855F7" in value


def test_seram_podcast_terms_use_mystery_theme_and_horror_hashtag():
    clip = ClipCandidate(
        index=1,
        start=0,
        end=60,
        duration=60,
        score=82,
        title="Podcast Cerita Seram Pendakian",
        reason="test",
        text="Penampakan pocong membuat suasana mencekam, tetapi ini adalah pengalaman narasumber.",
    )

    assert detect_visual_theme(clip) == "mystery"
    assert "#Misteri" in clip_topic_hashtags(clip)
    assert "#HororIndonesia" in clip_topic_hashtags(clip)


def test_reaction_cues_follow_conversation_and_stay_sparse():
    clip = ClipCandidate(
        index=1,
        start=100,
        end=140,
        duration=40,
        score=95,
        title="Obrolan Lucu dan Penuh Hikmah",
        reason="test",
        text="Percakapan lucu lalu ada kejutan dan rasa syukur.",
    )
    segments = [
        TranscriptSegment(101, 103, "Pembukaan dulu."),
        TranscriptSegment(105, 108, "Hahaha ini lucu banget sampai ngakak."),
        TranscriptSegment(109, 112, "Ternyata serius juga."),
        TranscriptSegment(114, 117, "Wow ternyata mengejutkan."),
        TranscriptSegment(124, 127, "Alhamdulillah ada hikmahnya."),
        TranscriptSegment(133, 136, "Kenapa bisa begitu?"),
    ]

    cues = detect_reaction_cues(clip, segments)

    assert [cue.kind for cue in cues] == ["laugh", "shock", "pray", "think"]
    assert cues[0].side == "right"
    assert cues[1].side == "left"
    assert all(b.start - a.start >= 5.5 for a, b in zip(cues, cues[1:]))


def test_reaction_svg_overlay_is_added_to_filter():
    cue = ReactionCue("laugh", 5, 6.85, "right", "lucu")

    value = enhanced_edit_filter(20, "clip.hook.txt", reaction_cues=[cue])

    assert "laugh.svg" in value
    assert "movie=" in value
    assert "overlay=" in value
    assert "between(t,5.000,6.850)" in value


def test_important_words_get_notice_sticker_and_matching_sound():
    clip = ClipCandidate(1, 0, 30, 30, 95, "Kunci Utama", "test", "Intinya ini penting.")
    segments = [
        TranscriptSegment(5, 8, "Intinya ini adalah kunci yang penting."),
    ]

    reactions = detect_reaction_cues(clip, segments)
    sounds = contextual_sound_effect_cues(30, reactions, emphasis_times=[])
    value = enhanced_edit_filter(30, "clip.hook.txt", reaction_cues=reactions)

    assert [cue.kind for cue in reactions] == ["important"]
    assert [cue.kind for cue in sounds] == ["important"]
    assert "important.svg" in value
    assert "text='NOTICE'" in value
    assert "text='!'" in value


def test_contextual_sound_effects_follow_reactions_and_avoid_duplicate_emphasis():
    reactions = [
        ReactionCue("laugh", 5, 6.85, "right", "lucu"),
        ReactionCue("shock", 12, 13.85, "left", "wow"),
        ReactionCue("pray", 20, 21.85, "right", "alhamdulillah"),
    ]

    cues = contextual_sound_effect_cues(
        30,
        reactions,
        emphasis_times=[5.5, 8.5, 16.0],
    )

    assert [cue.kind for cue in cues] == ["laugh", "emphasis", "shock", "emphasis", "pray"]
    assert all(right.start - left.start >= 3 for left, right in zip(cues, cues[1:]))
    assert all(0 < cue.volume <= 0.18 for cue in cues)


def test_contextual_audio_filter_mixes_sfx_under_voice_with_limiter():
    cues = [
        SoundEffectCue("shock", 4.5, 0.34, 105, 0.18, "wow"),
        SoundEffectCue("pray", 11, 0.38, 840, 0.065, "alhamdulillah"),
    ]

    value = contextual_audio_mix_filter("highpass=f=70,aresample=48000", cues)

    assert "[0:a:0]highpass=f=70" in value
    assert "sine=frequency=105" in value
    assert "adelay=delays=4500:all=1" in value
    assert "aecho=" in value
    assert "amix=inputs=3" in value
    assert "alimiter=limit=0.95" in value
    assert value.endswith("[audio_out]")


def test_social_caption_has_safe_relevant_fallback_without_ai():
    clip = ClipCandidate(
        index=1,
        start=0,
        end=60,
        duration=60,
        score=90,
        title="Mitos Jin yang Sering Dipercaya",
        reason="test",
        text="Kisah misteri jin dalam Islam ini perlu dilihat konteksnya.",
    )

    caption = fallback_social_caption(clip, ["Dakwah"])

    assert "Bedakan kisah, mitos, pengalaman, dan fakta" in caption
    assert "#Dakwah" in caption
    assert "#Misteri" in caption
    assert "#MitosAtauFakta" in caption


def test_landscape_compilation_caption_is_not_tagged_as_short():
    clip = ClipCandidate(
        index=1,
        start=0,
        end=300,
        duration=300,
        score=90,
        title="Lima Pelajaran Penting",
        reason="test",
        text="Rangkuman pembahasan yang memiliki konteks lengkap.",
    )

    caption = fallback_social_caption(clip, ["Hikmah"], long_form=True)

    assert "#Hikmah" in caption
    assert "#Shorts" not in caption


def test_source_channel_promos_are_boundaries_not_clip_content():
    segments = [
        TranscriptSegment(0, 20, "Ini penjelasan penting yang punya konteks lengkap."),
        TranscriptSegment(20, 40, "Ternyata jawabannya memberi pelajaran yang jelas."),
        TranscriptSegment(40, 44, "Terima kasih kepada LDTV dan jangan lupa subscribe."),
        TranscriptSegment(44, 65, "Sekarang masuk ke pembahasan berbeda yang bermanfaat."),
        TranscriptSegment(65, 86, "Intinya kita perlu memeriksa fakta sebelum percaya."),
    ]

    candidates = build_candidate_pool(segments, min_duration=18, max_duration=50)

    assert candidates
    assert is_source_branding_segment(segments[2])
    assert not is_source_branding_segment("Ikuti langkah berikut agar hasilnya benar.")
    assert all("LDTV" not in candidate.text for candidate in candidates)
    assert all(candidate.end <= 40 or candidate.start >= 44 for candidate in candidates)


def test_candidate_guard_frames_never_push_a_short_past_one_minute():
    segments = [
        TranscriptSegment(0, 30, "Tahukah kamu kenapa poin pertama ini penting?"),
        TranscriptSegment(30, 60, "Jawabannya memberi payoff yang jelas dan bermanfaat."),
    ]

    candidates = build_candidate_pool(segments, min_duration=15, max_duration=60)

    assert candidates
    assert all(candidate.duration <= 60 for candidate in candidates)


def test_source_channel_promos_are_removed_from_export_subtitles():
    segments = [
        TranscriptSegment(0, 5, "Poin utama yang bermanfaat."),
        TranscriptSegment(5, 8, "Silakan follow channel kami."),
        TranscriptSegment(8, 14, "Penjelasan dilanjutkan."),
    ]
    clip = ClipCandidate(1, 0, 14, 14, 90, "Poin Utama", "test", "test")

    clean = segments_for_clip(segments, clip)

    assert [segment.text for segment in clean] == [
        "Poin utama yang bermanfaat.",
        "Penjelasan dilanjutkan.",
    ]


def test_hook_banner_text_is_short_uppercase_and_wrapped():
    clip = ClipCandidate(
        index=1,
        start=0,
        end=60,
        duration=60,
        score=90,
        title="Inilah alasan penting kenapa keputusan pertama harus benar",
        reason="test",
        text="test",
    )

    value = hook_banner_text(clip)

    assert value == value.upper()
    assert len(value.splitlines()) <= 2
    assert all(len(line) <= 24 for line in value.splitlines())
