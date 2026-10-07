# -*- coding: utf-8 -*-
# MODULE 02: Settings-page builders and user-interface controls


def create_beast_progress_popup(total_runs, title_text="GDL BEAST MODE Progress"):
    try:
        dlg = JFrame()
        dlg.setTitle(str(title_text) + " - restore from taskbar")
        dlg.setSize(740, 420)
        try:
            dlg.setDefaultCloseOperation(0)  # DO_NOTHING_ON_CLOSE
        except:
            pass
        pane = JPanel()
        pane.setLayout(BoxLayout(pane, BoxLayout.Y_AXIS))
        pane.setBorder(BorderFactory.createEmptyBorder(14, 14, 14, 14))
        pane.setAlignmentX(0.0)

        phase = JLabel("BEAST MODE: preparing ImageJ queue")
        detail = JLabel(" ")
        fiji_agents = JLabel("Active Fiji agents (marker-confirmed): 0 / 1")
        try:
            fiji_agents.setFont(Font("SansSerif", Font.BOLD, 13))
        except:
            pass
        counters = JLabel(" ")
        timing = JLabel(" ")
        batch_image_status = JLabel("Batch image status: waiting")
        try:
            batch_image_status.setFont(Font("SansSerif", Font.BOLD, 13))
        except:
            pass
        imagej_label = JLabel("Current Fiji / ImageJ processing")
        imagej_bar = JProgressBar(0, max(1, int(total_runs)))
        imagej_bar.setStringPainted(True)
        jmp_label = JLabel("JMP worker pool")
        jmp_bar = JProgressBar(0, max(1, int(total_runs)))
        jmp_bar.setStringPainted(True)
        cancel_note = JLabel("Cancel stops the ImageJ queue, prevents new JMP launches, and terminates active JMP workers.")
        cancel_button = JButton("CANCEL EVERYTHING")
        style_dialog_button(cancel_button, False)

        def cancel_action(event):
            request_global_cancel("User pressed CANCEL EVERYTHING in BEAST MODE.")
            try:
                cancel_button.setEnabled(False)
                cancel_button.setText("Cancel requested...")
                cancel_note.setText("Stopping at the next safe point. Active JMP workers are being terminated now.")
                phase.setText("CANCEL REQUESTED - shutting down ImageJ/JMP work")
            except:
                pass

        cancel_button.addActionListener(cancel_action)

        class BeastProgressCloseListener(WindowAdapter):
            def windowClosing(self, event):
                cancel_action(event)

        dlg.addWindowListener(BeastProgressCloseListener())
        pane.add(phase)
        pane.add(Box.createVerticalStrut(7))
        pane.add(detail)
        pane.add(Box.createVerticalStrut(5))
        pane.add(fiji_agents)
        pane.add(Box.createVerticalStrut(5))
        pane.add(counters)
        pane.add(Box.createVerticalStrut(5))
        pane.add(timing)
        pane.add(Box.createVerticalStrut(5))
        pane.add(batch_image_status)
        pane.add(Box.createVerticalStrut(12))
        pane.add(imagej_label)
        pane.add(imagej_bar)
        pane.add(Box.createVerticalStrut(12))
        pane.add(jmp_label)
        pane.add(jmp_bar)
        pane.add(Box.createVerticalStrut(10))
        pane.add(cancel_note)
        pane.add(Box.createVerticalStrut(8))
        pane.add(cancel_button)
        dlg.add(pane)
        place_progress_dialog(dlg)
        dlg.setVisible(True)
        try:
            dlg.setAlwaysOnTop(False)
            dlg.setAutoRequestFocus(False)
        except:
            pass
        return {
            "dialog": dlg,
            "phase": phase,
            "detail": detail,
            "fiji_agents": fiji_agents,
            "active_fiji_agents": 0,
            "fiji_agent_limit": 1,
            "counters": counters,
            "timing": timing,
            "batch_image_status": batch_image_status,
            "imagej_bar": imagej_bar,
            "jmp_bar": jmp_bar,
            "cancel_button": cancel_button,
            "cancel_note": cancel_note,
            "start_time": time.time(),
            "update_sequence": 0,
            "applied_update_sequence": 0,
            "last_imagej_done": 0,
            "last_jmp_done": 0,
            "last_window_organize_time": 0.0,
            "last_update_time": time.time()
        }
    except Exception as e:
        IJ.log("Could not create BEAST MODE progress dialog: " + str(e))
        return None

def update_batch_image_completion_display(progress_ui, image_index, image_total, image_name, report_folder=""):
    text = "Image " + str(image_index) + " of " + str(image_total) + " complete"
    if str(image_name).strip() != "":
        text += " - " + str(image_name)
    try:
        IJ.showStatus(text)
    except:
        pass
    try:
        IJ.log("BATCH STATUS: " + text + ("; report folder=" + str(report_folder) if str(report_folder).strip() != "" else ""))
    except:
        pass
    if progress_ui is None:
        return
    try:
        label = progress_ui.get("batch_image_status", None)
        if label is not None:
            label.setText(text)
        if progress_ui.get("detail", None) is not None:
            progress_ui["detail"].setText(text)
        elif progress_ui.get("line2", None) is not None:
            progress_ui["line2"].setText(text)
        progress_ui["dialog"].repaint()
    except:
        pass

def update_beast_progress_popup(progress_ui, phase_text, detail_text, imagej_done, total_runs, jmp_done, jmp_active, error_count, active_fiji_agents=None, fiji_agent_limit=None):
    if progress_ui is None:
        return
    try:
        total_safe = max(1, int(total_runs))
        imagej_done_safe = max(0, min(int(imagej_done), total_safe))
        jmp_done_safe = max(0, min(int(jmp_done), total_safe))

        # Never let a temporarily stale OneDrive snapshot move either bar backward.
        imagej_done_safe = max(imagej_done_safe, int(progress_ui.get("last_imagej_done", 0)))
        jmp_done_safe = max(jmp_done_safe, int(progress_ui.get("last_jmp_done", 0)))
        progress_ui["last_imagej_done"] = imagej_done_safe
        progress_ui["last_jmp_done"] = jmp_done_safe
        progress_ui["last_update_time"] = time.time()

        elapsed = time.time() - float(progress_ui.get("start_time", time.time()))
        overall_done = imagej_done_safe + jmp_done_safe
        overall_total = total_safe * 2
        eta_text = "calculating"
        if overall_done > 0:
            remaining = max(0, overall_total - overall_done)
            eta_text = format_elapsed_seconds((elapsed / float(overall_done)) * float(remaining))

        if active_fiji_agents is not None:
            progress_ui["active_fiji_agents"] = max(0, int(active_fiji_agents))
        if fiji_agent_limit is not None:
            progress_ui["fiji_agent_limit"] = max(1, int(fiji_agent_limit))
        active_agents_safe = max(0, int(progress_ui.get("active_fiji_agents", 0)))
        agent_limit_safe = max(1, int(progress_ui.get("fiji_agent_limit", 1)))

        sequence = int(progress_ui.get("update_sequence", 0)) + 1
        progress_ui["update_sequence"] = sequence
        payload = {
            "sequence": sequence,
            "phase": str(phase_text),
            "detail": str(detail_text),
            "total": total_safe,
            "imagej_done": imagej_done_safe,
            "jmp_done": jmp_done_safe,
            "jmp_active": int(jmp_active),
            "errors": int(error_count),
            "active_agents": active_agents_safe,
            "agent_limit": agent_limit_safe,
            "elapsed": elapsed,
            "eta": eta_text
        }

        class BeastProgressUiRunnable(Runnable):
            def run(self):
                try:
                    if int(payload["sequence"]) < int(progress_ui.get("applied_update_sequence", 0)):
                        return
                    progress_ui["applied_update_sequence"] = int(payload["sequence"])
                    progress_ui["phase"].setText(payload["phase"])
                    progress_ui["detail"].setText(payload["detail"])
                    progress_ui["fiji_agents"].setText(
                        "Active Fiji agents (marker-confirmed): " + str(payload["active_agents"]) + " / " + str(payload["agent_limit"])
                    )
                    progress_ui["counters"].setText(
                        "Fiji agents active " + str(payload["active_agents"]) + "/" + str(payload["agent_limit"]) +
                        " | ImageJ " + str(payload["imagej_done"]) + "/" + str(payload["total"]) +
                        " | JMP completed " + str(payload["jmp_done"]) + "/" + str(payload["total"]) +
                        " | JMP active " + str(payload["jmp_active"]) +
                        " | errors " + str(payload["errors"])
                    )
                    progress_ui["timing"].setText(
                        "Elapsed " + format_elapsed_seconds(payload["elapsed"]) +
                        " | estimated remaining " + str(payload["eta"])
                    )
                    progress_ui["imagej_bar"].setMaximum(payload["total"])
                    progress_ui["imagej_bar"].setValue(payload["imagej_done"])
                    progress_ui["imagej_bar"].setString(str(payload["imagej_done"]) + " / " + str(payload["total"]))
                    progress_ui["jmp_bar"].setMaximum(payload["total"])
                    progress_ui["jmp_bar"].setValue(payload["jmp_done"])
                    progress_ui["jmp_bar"].setString(
                        str(payload["jmp_done"]) + " / " + str(payload["total"]) +
                        " completed; " + str(payload["jmp_active"]) + " active"
                    )
                    if global_cancel_requested():
                        progress_ui["phase"].setText("CANCEL REQUESTED - shutting down ImageJ/JMP work")
                        progress_ui["detail"].setText(str(RUN_CONTROL.get("cancel_reason", "")))
                    try:
                        progress_ui["dialog"].getContentPane().validate()
                    except:
                        pass
                    try:
                        progress_ui["dialog"].validate()
                    except:
                        pass
                    for repaint_component in [progress_ui.get("imagej_bar"), progress_ui.get("jmp_bar"), progress_ui.get("dialog")]:
                        try:
                            repaint_component.repaint()
                        except:
                            pass
                    try:
                        Toolkit.getDefaultToolkit().sync()
                    except:
                        pass
                except Exception as ui_error:
                    try:
                        IJ.log("BEAST progress UI update failed: " + str(ui_error))
                    except:
                        pass

        runnable = BeastProgressUiRunnable()
        try:
            if SwingUtilities.isEventDispatchThread():
                runnable.run()
            else:
                SwingUtilities.invokeLater(runnable)
        except:
            runnable.run()

        # Window tiling is expensive. Throttle it so it cannot starve Swing repainting.
        now_value = time.time()
        if now_value - float(progress_ui.get("last_window_organize_time", 0.0)) >= 2.0:
            progress_ui["last_window_organize_time"] = now_value
            organize_open_imagej_windows(progress_ui)
    except Exception as e:
        try:
            IJ.log("Could not update BEAST MODE progress dialog: " + str(e))
        except:
            pass

def add_checkbox_row(page, label, default_value):
    cb = JCheckBox(label)
    cb.setSelected(bool(default_value))
    cb.setMaximumSize(Dimension(820, 24))
    cb.setAlignmentX(0.0)
    cb.setOpaque(False)
    page.add(cb)
    page.add(Box.createVerticalStrut(2))
    return cb

def add_combo_row(page, label, items, default_value):
    row = JPanel(BorderLayout(8, 0))
    row.setMaximumSize(Dimension(820, 30))
    row.setAlignmentX(0.0)
    row.setOpaque(False)

    lab = JLabel(label)
    lab.setPreferredSize(Dimension(220, 22))
    row.add(lab, BorderLayout.WEST)

    combo = JComboBox(items)
    combo.setSelectedItem(default_value)
    row.add(combo, BorderLayout.CENTER)

    page.add(row)
    page.add(Box.createVerticalStrut(2))
    return combo

def add_section(page, title):
    lab = JLabel(title)
    try:
        lab.setFont(Font("SansSerif", Font.BOLD, 14))
    except:
        pass
    lab.setOpaque(True)
    lab.setBackground(Color(232, 240, 248))
    lab.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(190, 205, 220)),
        BorderFactory.createEmptyBorder(5, 8, 5, 8)
    ))
    lab.setMaximumSize(Dimension(820, 28))
    lab.setAlignmentX(0.0)
    page.add(Box.createVerticalStrut(4))
    page.add(lab)
    page.add(Box.createVerticalStrut(4))

def make_scroll(page):
    # Keep the settings pages usable on smaller screens: compact viewport + both scrollbars as needed.
    left_align_component_tree(page)
    scroll = JScrollPane(page)
    scroll.setAlignmentX(0.0)
    scroll.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED)
    scroll.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_AS_NEEDED)
    scroll.getVerticalScrollBar().setUnitIncrement(18)
    scroll.getHorizontalScrollBar().setUnitIncrement(18)
    scroll.setBorder(BorderFactory.createEmptyBorder())
    scroll.setPreferredSize(Dimension(720, 520))
    return scroll

def random_john_gdl_poem_html():
    poems = [
        "<html><div style='width:900px;'><b>John GDL: Startup Poem 1</b><br>"
        "John GDL stacked up hope with hydrogen flair,<br>"
        "He had an anode attitude and cathode-care,<br>"
        "Through membrane mayhem his protons would glide,<br>"
        "While electrons took the scenic external ride,<br>"
        "He kept his current positive, ohm by ohm,<br>"
        "Made water from trouble and powered every home,<br>"
        "Lord Soot got grounded when the clean stacks ran,<br>"
        "His smoke-screen empire fizzled under John's bright plan,<br>"
        "With catalyst courage and carbon-cloth soul,<br>"
        "John GDL cell-ebrated and saved the whole world.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 2</b><br>"
        "At sunrise John GDL sparked the lab awake,<br>"
        "He flipped from zero to hero with each fuel-cell stack he'd make,<br>"
        "His flow fields danced while the humid air would sing,<br>"
        "Every gasket sealed a bright electro-thing,<br>"
        "He never lost potential though resistance made a fuss,<br>"
        "He said, ohm my friends, clean power starts with us,<br>"
        "Baron Blacksmoke got phased when John's voltage hit the town,<br>"
        "His fossil plans depolarized and slowly melted down,<br>"
        "From GDL grit to membrane might, he made the future hum,<br>"
        "And every ampere cheered out loud: our John GDL has come.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 3</b><br>"
        "When storms rolled in, John GDL would never lose his charge,<br>"
        "He built a stack so pun-believable it powered ships and barges large,<br>"
        "His cathode jokes were airy and his anode jokes were hot,<br>"
        "He proton-moted progress at every clever plot,<br>"
        "He said the key to power was to stay in proper phase,<br>"
        "Then watt a miracle happened through the rainy haze,<br>"
        "The Smog King got grounded by the current of his dream,<br>"
        "His dirty crown met electrolyte and split apart at the seam,<br>"
        "With membrane swagger, porous pride, and GDL delight,<br>"
        "John lit the world so brightly that the dark resigned that night.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 4</b><br>"
        "John GDL walked factory floors with electrode in hand,<br>"
        "He turned each idle corner to a high-efficiency land,<br>"
        "He whispered to the flow plates, now channel all you can,<br>"
        "And every cell replied, we're amped to back the man,<br>"
        "His puns were fully charged and his patience never thin,<br>"
        "He always found the spark where lesser folks saw din,<br>"
        "Duke Diesel was baffled when the clean design took hold,<br>"
        "His carbon age got oxidized, his old excuses cold,<br>"
        "From ohmic woes to water's glow, he made the system roll,<br>"
        "And John GDL became the stack-star savior of the whole.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 5</b><br>"
        "In winter's chill John GDL kept every village warm,<br>"
        "He weathered every energy slump and every market storm,<br>"
        "His catalyst was kindness and his membrane game was tight,<br>"
        "He balanced all the reactants till the numbers came out right,<br>"
        "No one could resist him when he said resist less, friends,<br>"
        "For every little current drop was where a lesson ends,<br>"
        "Coal Count Crudmore got polarized and split into regret,<br>"
        "His heavy smoke was outperformed by John's clean water set,<br>"
        "With porous media wisdom and a pun for every cell,<br>"
        "John GDL made fuel feel cool and made the whole world well.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 6</b><br>"
        "John GDL once raced the dawn on rails of copper light,<br>"
        "He carried watts like battle flags and kept the future bright,<br>"
        "His stack was state-of-art villain-proof from base to crown,<br>"
        "Each proton crossing membranes kept the soot-lords shutting down,<br>"
        "He laughed, I'm in my element, while hydrogen would flow,<br>"
        "And every humble GDL helped clean ambition grow,<br>"
        "The Oil Ogre got out-designed by one relentless soul,<br>"
        "His empire lost coherence while John's systems stayed in control,<br>"
        "With current, voltage, pressure, heat, all tuned to sing as one,<br>"
        "John GDL proved hard work is how clean victories are won.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 7</b><br>"
        "At midnight John GDL debugged a stubborn stack by hand,<br>"
        "He said this issue's ohm-grown now, but watch me make it grand,<br>"
        "He traced each leak and pressure drop with an engineer's calm grace,<br>"
        "Then cathode-side chuckles put a smile back on each face,<br>"
        "His anode heart kept beating with a low-resistance tune,<br>"
        "And water dripped like applause beneath the silver moon,<br>"
        "General Grime was shocked to see the prototype take flight,<br>"
        "His schemes got open-circuited by one productive night,<br>"
        "With carbon cloth conviction and a membrane forged in zeal,<br>"
        "John GDL kept proving that clean power could be real.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 8</b><br>"
        "John GDL rode into town on a bus of fuel-cell fame,<br>"
        "Each stop became more energized the moment that he came,<br>"
        "He gave the grid a pep talk and the grid replied with cheers,<br>"
        "We've waited for this current for a hundred smoky years,<br>"
        "His puns were fully conductive and his work ethic first-rate,<br>"
        "He knew a bright electrolyte could change a city's fate,<br>"
        "Mister Soot got outmatched when the clean stack stole the show,<br>"
        "His plans had no good pathway for the charge he could not know,<br>"
        "So John GDL kept rolling with the membrane-minded crew,<br>"
        "And every mile said watt a guy, the future runs on you.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 9</b><br>"
        "In lecture halls John GDL turned chalk dust into sparks,<br>"
        "He graphed the rise of clean design in bright triumphant arcs,<br>"
        "He taught that every fuel-cell stack needs patience, grit, and care,<br>"
        "A cathode for the oxygen and courage in the air,<br>"
        "His students left with current goals and voltage in their stride,<br>"
        "For John's GDL example kept their confidence supplied,<br>"
        "Doctor Smog got schooled at last by data, work, and truth,<br>"
        "His tired claims got ion-swapped by John's electric youth,<br>"
        "With every porous layer set and every seal locked well,<br>"
        "He made the world say class dismissed, but long live John GDL.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 10</b><br>"
        "John GDL stood on the ridge where smokestacks blocked the sky,<br>"
        "He vowed to clear the air with stacks that never told a lie,<br>"
        "His membrane had momentum and his catalyst had style,<br>"
        "He turned each grim emission chart to something worth a smile,<br>"
        "He said let's keep this current and let the old waste go,<br>"
        "Then powered farms and workshops with a steady silver glow,<br>"
        "Captain Coal got phased right out when citizens could see,<br>"
        "That clean design with GDL grit could set the future free,<br>"
        "From anode dawn to cathode dusk his mission never fell,<br>"
        "The world found fresh potential in the hands of John GDL.</div></html>",

        "<html><div style='width:900px;'><b>John GDL: Startup Poem 11</b><br>"
        "John GDL loved pore maps, stacks, and every careful trace,<br>"
        "He brought a measured energy to every time and place,<br>"
        "He scaled the tiny details and he zoomed in on the good,<br>"
        "Then turned a lab of little wins to all the world's livelihood,<br>"
        "His proton wit was rapid and his GDL puns were prime,<br>"
        "He kept the clean solution flowing one hard-working line at a time,<br>"
        "The Tar Tycoon got left behind by one persistent guide,<br>"
        "Whose current of compassion kept the whole world unified,<br>"
        "So if your day needs voltage, let his legend start your spell,<br>"
        "For hope runs through the layers of our hero John GDL.</div></html>"
    ]
    try:
        return poems[random.randint(0, len(poems) - 1)]
    except:
        return poems[0]



# Embedded startup portrait thumbnail for the Dashboard poem card.
# This keeps the script standalone, so you do not need to keep a separate image file next to the macro.
JOHN_GDL_STARTUP_PHOTO_B64 = """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"""


def _java_signed_byte_array_from_b64(b64_text):
    # Jython can accidentally call ImageIcon(String filename) if raw base64 bytes
    # are left as a Python/Jython string. Force a real Java byte[] instead.
    raw = base64.b64decode(str(b64_text).replace("\n", "").replace("\r", "").replace(" ", ""))
    vals = []
    for i in range(len(raw)):
        ch = raw[i]
        try:
            v = ord(ch)
        except:
            v = int(ch)
        if v > 127:
            v = v - 256
        vals.append(v)
    return array(vals, 'b')



def gdl_v193_resource_path(filename):
    try:
        base_dir = str(globals().get("GDL_APP_DIR", ""))
    except:
        base_dir = ""
    if base_dir == "":
        try:
            base_dir = os.path.dirname(os.path.abspath(str(globals().get("__file__", ""))))
        except:
            base_dir = os.getcwd()
    module_dir = str(globals().get("GDL_MODULE_DIR_OVERRIDE", "")).strip()
    if module_dir == "":
        module_dir = os.path.join(base_dir, "GDL_code")
    return os.path.join(module_dir, "resources", str(filename))


def load_gdl_v193_resource_image(filename):
    path = gdl_v193_resource_path(filename)
    file_error = ""
    try:
        if os.path.isfile(path):
            buffered = ImageIO.read(File(path))
            if buffered is not None:
                return buffered
            file_error = "ImageIO could not decode resource"
        else:
            file_error = "Resource file is missing"
    except Exception as image_error:
        file_error = str(image_error)
    if str(filename).lower() == "john_gdl_startup.jpg" and JOHN_GDL_STARTUP_PHOTO_B64:
        try:
            byte_stream = ByteArrayInputStream(_java_signed_byte_array_from_b64(JOHN_GDL_STARTUP_PHOTO_B64))
            buffered = ImageIO.read(byte_stream)
            byte_stream.close()
            if buffered is not None:
                IJ.log("Loaded John GDL portrait from embedded fallback because the resource file failed: " + str(file_error))
                return buffered
        except Exception as fallback_error:
            file_error = str(file_error) + "; embedded fallback failed: " + str(fallback_error)
    raise Exception(str(file_error) + ": " + str(path))

def make_john_gdl_startup_photo_panel():
    panel = JPanel(BorderLayout())
    panel.setOpaque(False)
    panel.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(210, 195, 140)),
        BorderFactory.createEmptyBorder(6, 6, 6, 6)
    ))
    try:
        buffered = load_gdl_v193_resource_image("john_gdl_startup.jpg")

        # Keep the startup card predictable and avoid letting the image stretch the dashboard.
        target_w = 150
        target_h = 195
        scaled = buffered.getScaledInstance(target_w, target_h, Image.SCALE_SMOOTH)
        icon = ImageIcon(scaled)

        img_label = JLabel(icon)
        img_label.setHorizontalAlignment(JLabel.CENTER)
        img_label.setVerticalAlignment(JLabel.CENTER)
        img_label.setBorder(BorderFactory.createEmptyBorder(0, 0, 4, 0))
        panel.add(img_label, BorderLayout.CENTER)

        caption = JLabel("<html><center><b>Djong-Gie Oei (John GDL)</b></center></html>")
        caption.setHorizontalAlignment(JLabel.CENTER)
        panel.add(caption, BorderLayout.SOUTH)
    except Exception as e:
        IJ.log("Could not load startup portrait: " + str(e))
        panel.add(JLabel("<html><center><b>Djong-Gie Oei (John GDL)</b><br>portrait unavailable</center></html>"), BorderLayout.CENTER)
    panel.setPreferredSize(Dimension(178, 235))
    panel.setMinimumSize(Dimension(178, 235))
    panel.setMaximumSize(Dimension(178, 235))
    return panel

def populate_v193_capture_page(capture_page, fields):

    cap_banner = JPanel(BorderLayout())
    cap_banner.setBackground(Color(255, 245, 220))
    cap_banner.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(215, 170, 90)),
        BorderFactory.createEmptyBorder(14, 16, 14, 16)
    ))
    cap_banner.setMaximumSize(Dimension(820, 70))
    cap_banner.setPreferredSize(Dimension(820, 70))
    cap_banner.setAlignmentX(0.0)
    cap_banner.add(JLabel("<html><div style='width:720px;'><b>YOURE A BETA image capture fork</b><br>Capture active ImageJ/camera frames, set scale once, then save calibrated TIFFs for the batch.</div></html>"), BorderLayout.CENTER)
    capture_page.add(cap_banner)
    capture_page.add(Box.createVerticalStrut(12))

    capture_card = JPanel()
    capture_card.setLayout(BoxLayout(capture_card, BoxLayout.Y_AXIS))
    capture_card.setBackground(Color(255, 255, 255))
    capture_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(200, 210, 220)),
        BorderFactory.createEmptyBorder(12, 12, 12, 12)
    ))
    capture_card.setMaximumSize(Dimension(820, 250))
    capture_card.setPreferredSize(Dimension(820, 250))
    capture_card.setAlignmentX(0.0)
    capture_page.add(capture_card)

    add_section(capture_card, "Image capture workflow")
    fields["image_capture_enabled"] = add_checkbox_row(capture_card, "Enable image capturing", DEFAULTS["image_capture_enabled"])
    fields["image_capture_mode"] = add_combo_row(capture_card, "Capture mode", ["Capture scaled TIFFs only, stop", "Capture scaled TIFFs, then run analysis"], DEFAULTS["image_capture_mode"])
    fields["image_capture_count"] = add_text_row(capture_card, "Sample image count", DEFAULTS["image_capture_count"], 20)
    fields["image_capture_batch_name"] = add_text_row(capture_card, "Optional batch name", DEFAULTS["image_capture_batch_name"], 30)
    fields["image_capture_scale_known_length_mm"] = add_text_row(capture_card, "Known scale-bar distance, mm", DEFAULTS["image_capture_scale_known_length_mm"], 20)
    fields["image_capture_save_scale_frame"] = add_checkbox_row(capture_card, "Save scale-frame TIFF", DEFAULTS["image_capture_save_scale_frame"])
    fields["image_capture_keep_captured_windows_open"] = add_checkbox_row(capture_card, "Keep captured windows open while testing", DEFAULTS["image_capture_keep_captured_windows_open"])

    capture_page.add(Box.createVerticalStrut(10))

    live_card = JPanel()
    live_card.setLayout(BoxLayout(live_card, BoxLayout.Y_AXIS))
    live_card.setBackground(Color(255, 255, 255))
    live_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(200, 210, 220)),
        BorderFactory.createEmptyBorder(10, 12, 10, 12)
    ))
    live_card.setMaximumSize(Dimension(820, 205))
    live_card.setPreferredSize(Dimension(820, 205))
    live_card.setAlignmentX(0.0)
    capture_page.add(live_card)

    add_section(live_card, "Live view helper")
    fields["image_capture_try_open_live_view"] = add_checkbox_row(live_card, "Try to auto-open live view when capture starts", DEFAULTS["image_capture_try_open_live_view"])
    fields["image_capture_live_view_command"] = add_combo_row(live_card, "Live-view opener", ["Auto-detect common live-view command", "Micro-Manager Studio", "Micro-Manager", "Video Capture...", "Video Capture...", "Capture Video...", "Capture Video...", "Webcam Capture...", "USB Camera...", "TWAIN Acquire...", "Do not auto-open"], DEFAULTS["image_capture_live_view_command"])
    fields["image_capture_show_live_view_directions"] = add_checkbox_row(live_card, "Show live-view directions before scale capture", DEFAULTS["image_capture_show_live_view_directions"])

    capture_page.add(Box.createVerticalStrut(10))
    directions_card = JPanel(BorderLayout())
    directions_card.setBackground(Color(255, 252, 238))
    directions_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(220, 190, 120)),
        BorderFactory.createEmptyBorder(10, 12, 10, 12)
    ))
    directions_card.setMaximumSize(Dimension(820, 125))
    directions_card.setPreferredSize(Dimension(820, 125))
    directions_card.setAlignmentX(0.0)
    directions_card.add(JLabel("<html><div style='width:720px;'><b>Getting to live view</b><br>1. Plug in the microscope/camera before starting Fiji.<br>2. If auto-open does not find a plugin, try Fiji menus such as <b>Plugins &gt; Micro-Manager</b>, <b>Plugins &gt; Acquisition/Camera</b>, <b>USB Camera</b>, or <b>TWAIN Acquire</b> if those plugins are installed.<br>3. Once a live image window is open, click that image window before pressing Capture.</div></html>"), BorderLayout.CENTER)
    capture_page.add(directions_card)

    capture_page.add(Box.createVerticalStrut(12))
    workflow_card = JPanel(BorderLayout())
    workflow_card.setBackground(Color(245, 250, 255))
    workflow_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(185, 205, 225)),
        BorderFactory.createEmptyBorder(12, 14, 12, 14)
    ))
    workflow_card.setMaximumSize(Dimension(820, 120))
    workflow_card.setPreferredSize(Dimension(820, 120))
    workflow_card.setAlignmentX(0.0)
    workflow_card.add(JLabel("<html><div style='width:720px;'><b>How it runs</b><br>1. Open the camera/live preview and click that image window.<br>2. Capture the scale frame; fix the edge-to-edge line if needed, then enter known distance.<br>3. Capture samples as scaled TIFFs. Analysis mode runs from those TIFFs.</div></html>"), BorderLayout.CENTER)
    capture_page.add(workflow_card)
    capture_page.add(Box.createVerticalGlue())


def populate_v193_scale_page(scale_page, fields):
    add_section(scale_page, "Set Scale Only")
    fields["set_scale_only_mode"] = add_checkbox_row(scale_page, "Set scale only and stop; do not threshold, analyze, JMP, or make reports", DEFAULTS["set_scale_only_mode"])

    add_section(scale_page, "Swift Imaging 3.0 Magnification Table")
    fields["swift_magn_scale_enabled"] = add_checkbox_row(scale_page, "Read and apply scale from a Swift Imaging .magn table before processing", DEFAULTS["swift_magn_scale_enabled"])
    fields["swift_magn_filename"] = add_text_row(scale_page, "Magnification-table filename", DEFAULTS["swift_magn_filename"], 28)

    # v199: populate the objective/profile selector directly from the bundled
    # Swift Imaging .magn table. AUTO remains available for mixed batches whose
    # image or folder names contain the profile token (for example 4X or 10X).
    swift_profile_choices = ["AUTO"]
    swift_profile_summary = []
    try:
        bundled_magn = os.path.join(
            os.environ.get("GDL_SWIFT_FOLDER", "").strip() or os.path.join(quick_run_app_dir(), "Swift Magnification Tables"),
            str(DEFAULTS.get("swift_magn_filename", "Imaging.magn"))
        )
        if os.path.isfile(bundled_magn):
            decoded_profiles = parse_swift_magnification_table(bundled_magn)
            for decoded_profile in decoded_profiles:
                decoded_name = str(decoded_profile.get("name", "")).strip()
                if decoded_name != "" and decoded_name not in swift_profile_choices:
                    swift_profile_choices.append(decoded_name)
                try:
                    decoded_px_m = float(decoded_profile.get("resolution_pixels_per_meter", 0.0))
                    decoded_um_px = 1000000.0 / decoded_px_m if decoded_px_m > 0.0 else 0.0
                    swift_profile_summary.append(
                        decoded_name + " = " + ("%.6f" % decoded_um_px) + " um/pixel"
                    )
                except:
                    pass
    except Exception as swift_profile_ui_error:
        try:
            IJ.log("Could not populate Swift magnification-profile dropdown: " + str(swift_profile_ui_error))
        except:
            pass

    default_swift_profile = str(DEFAULTS.get("swift_magn_profile_name", "AUTO"))
    if default_swift_profile not in swift_profile_choices:
        swift_profile_choices.append(default_swift_profile)
    fields["swift_magn_profile_name"] = add_combo_row(
        scale_page,
        "Swift objective / magnification profile",
        swift_profile_choices,
        default_swift_profile
    )
    try:
        fields["swift_magn_profile_name"].setEditable(True)
    except:
        pass
    if len(swift_profile_summary) > 0:
        scale_page.add(JLabel(
            "<html><div style='width:760px;'><b>Profiles read from bundled Imaging.magn:</b> " +
            " &nbsp; | &nbsp; ".join(swift_profile_summary) +
            ". Choose a fixed profile for a single-objective batch. Use AUTO only when the image/folder name contains the profile, such as 4X or 10X.</div></html>"
        ))

    fields["swift_magn_search_parent_levels"] = add_text_row(scale_page, "Parent folders to search above each image folder", DEFAULTS["swift_magn_search_parent_levels"], 20)
    fields["swift_magn_use_bundle_fallback"] = add_checkbox_row(scale_page, "Also use the bundled Swift Magnification Tables folder", DEFAULTS["swift_magn_use_bundle_fallback"])
    fields["swift_magn_override_existing_scale"] = add_checkbox_row(scale_page, "Override an existing image calibration with the Swift table", DEFAULTS["swift_magn_override_existing_scale"])
    scale_page.add(JLabel("<html><div style='width:760px;'>Search order: image folder → parent folders → bundled table folder. Swift Resolution is interpreted as pixels per meter (px/m). v199 supports multiple profiles in the same Imaging.magn file; select 4X or 10X explicitly, or use AUTO for profile-labeled image/folder names.</div></html>"))

    add_section(scale_page, "Manual / Red-Line Fallback")
    fields["set_scale_direct_enabled"] = add_checkbox_row(scale_page, "Use manual scale below when Swift-table scaling is unavailable", DEFAULTS["set_scale_direct_enabled"])
    fields["set_scale_direct_mm_per_pixel"] = add_text_row(scale_page, "Manual scale, mm per pixel; 0 = ignore", DEFAULTS["set_scale_direct_mm_per_pixel"], 20)
    fields["set_scale_direct_pixels_per_mm"] = add_text_row(scale_page, "Manual scale, pixels per mm; 0 = ignore", DEFAULTS["set_scale_direct_pixels_per_mm"], 20)
    fields["auto_scale_save_tif_enabled"] = add_checkbox_row(scale_page, "Save calibrated TIFF", DEFAULTS["auto_scale_save_tif_enabled"])
    fields["auto_scale_save_tif_subfolder_enabled"] = add_checkbox_row(scale_page, "Save calibrated TIFFs in folder named Scaled image", DEFAULTS["auto_scale_save_tif_subfolder_enabled"])
    fields["auto_scale_replace_png_with_tif_enabled"] = add_checkbox_row(scale_page, "Replace PNG/JPG workflow with calibrated TIFF; move original image to backup", DEFAULTS["auto_scale_replace_png_with_tif_enabled"])
    fields["auto_scale_blue_ocr_enabled"] = add_checkbox_row(scale_page, "Try to read orange/blue distance text and prefill actual distance; default OFF", DEFAULTS["auto_scale_blue_ocr_enabled"])
    fields["auto_scale_blue_search_padding_px"] = add_text_row(scale_page, "Orange/blue text search distance around red line, pixels", DEFAULTS["auto_scale_blue_search_padding_px"], 20)
    fields["auto_scale_preview_zoom_factor"] = add_text_row(scale_page, "Scale preview zoom factor, 1-10x", DEFAULTS["auto_scale_preview_zoom_factor"], 20)
    scale_page.add(JLabel("If direct scale is off, this mode uses the red reference line workflow and lets you confirm/correct the actual distance."))
    scale_page.add(JLabel("Orange/blue label inference assumes the on-screen dimension is between 0.100 and 2.000 mm."))
    scale_page.add(JLabel("For PNG inputs, calibrated TIFFs are saved in Scaled image and normal analysis uses those TIFF files so report names stay consistent."))
    add_section(scale_page, "Red/Orange Reference Scale")
    scale_page.add(JLabel("Red line = detected pixel length. Orange/blue label reader is optional and OFF by default. When off, the script just shows the cropped scale region and lets you type the actual distance."))


def populate_v193_general_jmp_page(general, fields):
    add_section(general, "Run mode")
    fields["batch_enabled"] = add_checkbox_row(general, "Batch mode: process every image in a selected folder", DEFAULTS["batch_enabled"])
    fields["include_subfolders"] = add_checkbox_row(general, "Batch mode: include subfolders", DEFAULTS["include_subfolders"])
    fields["crop_count"] = add_text_row(general, "Number of crop regions to process; 0 = no crops", DEFAULTS["crop_count"], 20)
    fields["crop_mode"] = add_combo_row(general, "Crop mode", ["Manual select", "Auto cropped grid"], DEFAULTS["crop_mode"])
    fields["crop_prompt_each_image"] = add_checkbox_row(general, "Ask crop count/mode for each image; only used when crop count is > 0", DEFAULTS["crop_prompt_each_image"])
    fields["fancy_progress_enabled"] = add_checkbox_row(general, "Show fancy progress window during processing", DEFAULTS["fancy_progress_enabled"])
    fields["close_windows_when_finished"] = add_checkbox_row(general, "Close all ImageJ/Fiji windows when finished", DEFAULTS["close_windows_when_finished"])
    fields["close_jmp_windows_when_finished"] = add_checkbox_row(general, "Close JMP windows/tables created by each run when finished", DEFAULTS["close_jmp_windows_when_finished"])

    add_section(general, "BEAST MODE quick control")
    fields["beast_mode_enabled"] = add_checkbox_row(general, "Enable BEAST MODE", DEFAULTS["beast_mode_enabled"])
    general.add(JLabel("Detailed Fiji/JMP worker controls remain on the Advanced BEAST MODE page."))

    add_section(general, "Quick toggles")
    fields["manual_measurements_enabled"] = add_checkbox_row(general, "First-page quick toggle: enable all manual measurements", DEFAULTS["manual_measurements_enabled"])

    add_section(general, "JMP launch")
    fields["launch_jmp"] = add_checkbox_row(general, "Use the bounded parallel JMP pool", DEFAULTS["launch_jmp"])
    fields["max_jmp_launches"] = add_text_row(general, "Maximum simultaneous JMP instances", DEFAULTS["max_jmp_launches"], 20)
    fields["jmp_streaming_enabled"] = add_checkbox_row(general, "Start JMP while Fiji is still processing", DEFAULTS["jmp_streaming_enabled"])
    fields["jmp_start_after_fiji_runs"] = add_text_row(general, "Start JMP after this many completed Fiji runs", DEFAULTS["jmp_start_after_fiji_runs"], 20)
    fields["jmp_exe"] = add_text_row(general, "JMP executable path", DEFAULTS["jmp_exe"], 60)

    add_section(general, "JMP histogram display")
    fields["jmp_hist_graph_width"] = add_text_row(general, "Histogram image width, pixels", DEFAULTS["jmp_hist_graph_width"], 20)
    fields["jmp_hist_graph_height"] = add_text_row(general, "Histogram image height, pixels", DEFAULTS["jmp_hist_graph_height"], 20)
    fields["jmp_hist_show_legend"] = add_checkbox_row(general, "Show histogram legend", DEFAULTS["jmp_hist_show_legend"])
    fields["jmp_hist_show_graph_titles"] = add_checkbox_row(general, "Show histogram graph titles", DEFAULTS["jmp_hist_show_graph_titles"])
    fields["jmp_hist_show_axis_titles"] = add_checkbox_row(general, "Show histogram axis titles", DEFAULTS["jmp_hist_show_axis_titles"])
    fields["jmp_hist_trim_trailing_zeros"] = add_checkbox_row(general, "Trim trailing zeros on histogram axis labels", DEFAULTS["jmp_hist_trim_trailing_zeros"])
    fields["jmp_hist_axis_pad_percent"] = add_text_row(general, "Histogram X-axis padding percent", DEFAULTS["jmp_hist_axis_pad_percent"], 20)
    fields["jmp_hist_auto_binning"] = add_checkbox_row(general, "Use JMP automatic histogram binning", DEFAULTS["jmp_hist_auto_binning"])
    fields["jmp_hist_max_bins"] = add_text_row(general, "Fixed-bin fallback/default histogram bins", DEFAULTS["jmp_hist_max_bins"], 20)

    add_section(general, "EPD histogram controls")
    fields["jmp_hist_epd_title"] = add_text_row(general, "EPD histogram title", DEFAULTS["jmp_hist_epd_title"], 40)
    fields["jmp_hist_epd_x_axis_title"] = add_text_row(general, "EPD X-axis title", DEFAULTS["jmp_hist_epd_x_axis_title"], 40)
    fields["jmp_hist_epd_y_axis_title"] = add_text_row(general, "EPD Y-axis title", DEFAULTS["jmp_hist_epd_y_axis_title"], 40)
    fields["jmp_hist_epd_bins"] = add_text_row(general, "EPD histogram bins", DEFAULTS["jmp_hist_epd_bins"], 20)
    fields["jmp_hist_epd_x_min"] = add_text_row(general, "EPD X-axis min [mm]", DEFAULTS["jmp_hist_epd_x_min"], 20)
    fields["jmp_hist_epd_x_max"] = add_text_row(general, "EPD X-axis max [mm] (0 = auto)", DEFAULTS["jmp_hist_epd_x_max"], 20)
    fields["jmp_hist_epd_major_tick"] = add_text_row(general, "EPD X-axis major tick [mm] (0 = auto)", DEFAULTS["jmp_hist_epd_major_tick"], 20)
    fields["jmp_hist_epd_x_minor_ticks"] = add_text_row(general, "EPD X-axis minor ticks", DEFAULTS["jmp_hist_epd_x_minor_ticks"], 20)
    fields["jmp_hist_epd_y_max"] = add_text_row(general, "EPD Y-axis max count (0 = auto)", DEFAULTS["jmp_hist_epd_y_max"], 20)
    fields["jmp_hist_epd_y_major_tick"] = add_text_row(general, "EPD Y-axis major tick count (0 = auto)", DEFAULTS["jmp_hist_epd_y_major_tick"], 20)
    fields["jmp_hist_epd_y_minor_ticks"] = add_text_row(general, "EPD Y-axis minor ticks", DEFAULTS["jmp_hist_epd_y_minor_ticks"], 20)
    fields["jmp_epd_show_cutoff_lines"] = add_checkbox_row(general, "Show EPD cutoff lines on EPD histogram", DEFAULTS["jmp_epd_show_cutoff_lines"])
    fields["jmp_epd_hist_round_filter_enabled"] = add_checkbox_row(general, "EPD histogram: filter by minimum roundness", DEFAULTS["jmp_epd_hist_round_filter_enabled"])
    fields["jmp_epd_hist_round_filter_min"] = add_text_row(general, "EPD histogram minimum roundness", DEFAULTS["jmp_epd_hist_round_filter_min"], 20)

    add_section(general, "Roundness histogram controls")
    fields["jmp_hist_round_title"] = add_text_row(general, "Roundness histogram title", DEFAULTS["jmp_hist_round_title"], 40)
    fields["jmp_hist_round_x_axis_title"] = add_text_row(general, "Roundness X-axis title", DEFAULTS["jmp_hist_round_x_axis_title"], 40)
    fields["jmp_hist_round_y_axis_title"] = add_text_row(general, "Roundness Y-axis title", DEFAULTS["jmp_hist_round_y_axis_title"], 40)
    fields["jmp_hist_round_bins"] = add_text_row(general, "Roundness histogram bins", DEFAULTS["jmp_hist_round_bins"], 20)
    fields["jmp_hist_round_x_min"] = add_text_row(general, "Roundness X-axis min", DEFAULTS["jmp_hist_round_x_min"], 20)
    fields["jmp_hist_round_x_max"] = add_text_row(general, "Roundness X-axis max (0 = auto)", DEFAULTS["jmp_hist_round_x_max"], 20)
    fields["jmp_hist_round_x_major_tick"] = add_text_row(general, "Roundness X-axis major tick (0 = auto)", DEFAULTS["jmp_hist_round_x_major_tick"], 20)
    fields["jmp_hist_round_x_minor_ticks"] = add_text_row(general, "Roundness X-axis minor ticks", DEFAULTS["jmp_hist_round_x_minor_ticks"], 20)
    fields["jmp_hist_round_y_max"] = add_text_row(general, "Roundness Y-axis max count (0 = auto)", DEFAULTS["jmp_hist_round_y_max"], 20)
    fields["jmp_hist_round_y_major_tick"] = add_text_row(general, "Roundness Y-axis major tick count (0 = auto)", DEFAULTS["jmp_hist_round_y_major_tick"], 20)
    fields["jmp_hist_round_y_minor_ticks"] = add_text_row(general, "Roundness Y-axis minor ticks", DEFAULTS["jmp_hist_round_y_minor_ticks"], 20)

    add_section(general, "Circularity histogram controls")
    fields["jmp_hist_circ_title"] = add_text_row(general, "Circularity histogram title", DEFAULTS["jmp_hist_circ_title"], 40)
    fields["jmp_hist_circ_x_axis_title"] = add_text_row(general, "Circularity X-axis title", DEFAULTS["jmp_hist_circ_x_axis_title"], 40)
    fields["jmp_hist_circ_y_axis_title"] = add_text_row(general, "Circularity Y-axis title", DEFAULTS["jmp_hist_circ_y_axis_title"], 40)
    fields["jmp_hist_circ_bins"] = add_text_row(general, "Circularity histogram bins", DEFAULTS["jmp_hist_circ_bins"], 20)
    fields["jmp_hist_circ_x_min"] = add_text_row(general, "Circularity X-axis min", DEFAULTS["jmp_hist_circ_x_min"], 20)
    fields["jmp_hist_circ_x_max"] = add_text_row(general, "Circularity X-axis max (0 = auto)", DEFAULTS["jmp_hist_circ_x_max"], 20)
    fields["jmp_hist_circ_x_major_tick"] = add_text_row(general, "Circularity X-axis major tick (0 = auto)", DEFAULTS["jmp_hist_circ_x_major_tick"], 20)
    fields["jmp_hist_circ_x_minor_ticks"] = add_text_row(general, "Circularity X-axis minor ticks", DEFAULTS["jmp_hist_circ_x_minor_ticks"], 20)
    fields["jmp_hist_circ_y_max"] = add_text_row(general, "Circularity Y-axis max count (0 = auto)", DEFAULTS["jmp_hist_circ_y_max"], 20)
    fields["jmp_hist_circ_y_major_tick"] = add_text_row(general, "Circularity Y-axis major tick count (0 = auto)", DEFAULTS["jmp_hist_circ_y_major_tick"], 20)
    fields["jmp_hist_circ_y_minor_ticks"] = add_text_row(general, "Circularity Y-axis minor ticks", DEFAULTS["jmp_hist_circ_y_minor_ticks"], 20)

    fields["jmp_summary_use_all_detected"] = add_checkbox_row(general, "Legacy option disabled: JMP statistics/histograms use cleaned EPD data; selected between-band count uses all detected pores", False)
    try:
        fields["jmp_summary_use_all_detected"].setEnabled(False)
    except:
        pass

    add_section(general, "Flag weird pores")
    fields["flag_weird_pores_enabled"] = add_checkbox_row(general, "Add weird/outlier pore table to report", DEFAULTS["flag_weird_pores_enabled"])
    fields["flag_weird_epd_above"] = add_text_row(general, "Flag EPD above, mm", DEFAULTS["flag_weird_epd_above"], 20)
    fields["flag_weird_circularity_below"] = add_text_row(general, "Flag Circularity below", DEFAULTS["flag_weird_circularity_below"], 20)
    fields["flag_weird_roundness_below"] = add_text_row(general, "Flag Roundness below", DEFAULTS["flag_weird_roundness_below"], 20)
    fields["flag_weird_roundness_above"] = add_text_row(general, "Flag Roundness above", DEFAULTS["flag_weird_roundness_above"], 20)

    add_section(general, "Output / CSV")
    fields["csv_decimals"] = add_text_row(general, "CSV decimal places", DEFAULTS["csv_decimals"], 20)
    fields["imagej_results_precision"] = add_text_row(general, "Force ImageJ Results precision", DEFAULTS["imagej_results_precision"], 20)
    fields["docx_report_decimals"] = add_text_row(general, "DOCX max decimal places; trailing zeros removed", DEFAULTS["docx_report_decimals"], 20)

    add_section(general, "Defaults")
    fields["save_settings_as_default"] = add_checkbox_row(general, "Save these settings as defaults for next run", DEFAULTS["save_settings_as_default"])
    fields["open_output_folder_when_done"] = add_checkbox_row(general, "Open output folder when finished", DEFAULTS["open_output_folder_when_done"])

    add_section(general, "Named presets")
    fields["preset_name"] = add_text_row(general, "Preset name", DEFAULTS["preset_name"], 30)
    fields["load_named_preset"] = add_checkbox_row(general, "Load this named preset when OK is clicked", DEFAULTS["load_named_preset"])
    fields["save_named_preset"] = add_checkbox_row(general, "Save current settings to this named preset", DEFAULTS["save_named_preset"])



def populate_v193_beast_page(beast, fields):
    beast_banner = JPanel(BorderLayout())
    beast_banner.setBackground(Color(245, 225, 225))
    beast_banner.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(175, 70, 70)),
        BorderFactory.createEmptyBorder(14, 16, 14, 16)
    ))
    beast_banner.setMaximumSize(Dimension(820, 105))
    beast_banner.add(JLabel("<html><div style='width:720px;'><b>BEAST MODE</b><br>For unattended runs. v209 uses a shared dynamic queue with one exact run per disposable Fiji agent process. When an agent finishes, its slot immediately takes the next queued run; slow sweep settings can no longer strand work on one static worker. A crashed/stalled agent retries only its current run. JMP starts after the Fiji queue settles for reliability. The three-sheet XLSX remains the primary output.</div></html>"), BorderLayout.CENTER)
    beast.add(beast_banner)
    beast.add(Box.createVerticalStrut(10))

    add_section(beast, "BEAST MODE control")
    beast.add(JLabel("Enable or disable BEAST MODE from the General + JMP page."))
    fields["beast_parallel_fiji_enabled"] = add_checkbox_row(beast, "Use dynamic disposable Fiji agents", DEFAULTS["beast_parallel_fiji_enabled"])
    fields["beast_show_fiji_worker_windows"] = add_checkbox_row(beast, "Show separate Fiji worker windows (unchecked = headless)", DEFAULTS["beast_show_fiji_worker_windows"])
    fields["beast_fiji_parallel_instances"] = add_text_row(beast, "Parallel Fiji workers (1-16; default 4)", DEFAULTS["beast_fiji_parallel_instances"], 20)
    fields["beast_fiji_fallback_to_controller"] = add_checkbox_row(beast, "Automatically rerun missing worker jobs in this Fiji instance", DEFAULTS["beast_fiji_fallback_to_controller"])
    fields["beast_fiji_worker_timeout_sec"] = add_text_row(beast, "Emergency maximum Fiji agent process time, seconds", DEFAULTS["beast_fiji_worker_timeout_sec"], 20)
    fields["beast_fiji_no_progress_timeout_sec"] = add_text_row(beast, "Restart disposable agent after no algorithmic progress, seconds (v209 minimum 900)", DEFAULTS["beast_fiji_no_progress_timeout_sec"], 20)
    fields["beast_fiji_heartbeat_interval_sec"] = add_text_row(beast, "Agent heartbeat interval, seconds", DEFAULTS["beast_fiji_heartbeat_interval_sec"], 20)
    fields["beast_fiji_heartbeat_timeout_sec"] = add_text_row(beast, "Restart agent after heartbeat is missing, seconds", DEFAULTS["beast_fiji_heartbeat_timeout_sec"], 20)
    fields["beast_fiji_claim_timeout_sec"] = add_text_row(beast, "Agent real-job claim timeout, seconds", DEFAULTS["beast_fiji_claim_timeout_sec"], 20)
    fields["beast_fiji_job_timeout_sec"] = add_text_row(beast, "Hard maximum for one ImageJ run, seconds (v209 minimum 1800)", DEFAULTS["beast_fiji_job_timeout_sec"], 20)
    fields["beast_fiji_runtime_retries"] = add_text_row(beast, "Per-run disposable-agent retries before controller fallback", DEFAULTS["beast_fiji_runtime_retries"], 20)
    fields["beast_fiji_launch_stagger_sec"] = add_text_row(beast, "Delay between Fiji worker launches, seconds", DEFAULTS["beast_fiji_launch_stagger_sec"], 20)
    fields["beast_fiji_worker_startup_timeout_sec"] = add_text_row(beast, "Fiji worker startup-marker timeout, seconds", DEFAULTS["beast_fiji_worker_startup_timeout_sec"], 20)
    fields["beast_preflight_enabled"] = add_checkbox_row(beast, "Run Fiji/JMP launch self-tests before opening progress", DEFAULTS["beast_preflight_enabled"])
    fields["beast_preflight_timeout_sec"] = add_text_row(beast, "Fiji preflight total marker budget, seconds", DEFAULTS["beast_preflight_timeout_sec"], 20)
    fields["beast_jmp_parallel_instances"] = add_text_row(beast, "Parallel JMP instances", DEFAULTS["beast_jmp_parallel_instances"], 20)
    fields["beast_jmp_safe_launch_enabled"] = add_checkbox_row(beast, "Crash-resilient parallel JMP mode (keeps all configured slots active)", DEFAULTS.get("beast_jmp_safe_launch_enabled", True))
    fields["beast_jmp_minimized_launch_enabled"] = add_checkbox_row(beast, "Launch JMP workers minimized", DEFAULTS.get("beast_jmp_minimized_launch_enabled", True))
    fields["beast_jmp_isolated_temp_enabled"] = add_checkbox_row(beast, "Use an isolated TEMP folder for every JMP worker", DEFAULTS.get("beast_jmp_isolated_temp_enabled", True))
    fields["beast_jmp_streaming_enabled"] = add_checkbox_row(beast, "Start JMP while Fiji is still processing (single/controller Fiji; dynamic agents defer JMP)", DEFAULTS["beast_jmp_streaming_enabled"])
    fields["beast_jmp_start_after_fiji_runs"] = add_text_row(beast, "Start JMP after this many Fiji runs finish", DEFAULTS["beast_jmp_start_after_fiji_runs"], 20)
    fields["beast_create_graph_word_report"] = add_checkbox_row(beast, "Create JMP graphs/histograms in BEAST MODE", DEFAULTS["beast_create_graph_word_report"])
    beast_report_modes = list(DEFAULTS.get("word_report_mode_options", ["No Word reports", "Combined Word report", "Individual by image", "Completely separate individual reports", "Individual by image + combined", "Completely separate individual reports + combined"]))
    beast_report_default = str(DEFAULTS.get("beast_word_report_mode", "Combined Word report"))
    if beast_report_default not in beast_report_modes:
        beast_report_modes.append(beast_report_default)
    fields["beast_word_report_mode"] = add_combo_row(beast, "Legacy BEAST report output (mirrors Report card)", beast_report_modes, beast_report_default)
    try:
        fields["beast_word_report_mode"].setEnabled(False)
    except:
        pass
    beast.add(JLabel("v209: BEAST uses the single Word report output dropdown on the Report card. This legacy field is display-only and cannot override it."))
    beast.add(JLabel("Individual by image = one DOCX per original input image containing all of its crops/sweeps."))
    beast.add(JLabel("Completely separate individual reports = exactly one DOCX per completed run/crop/sweep result, with matching summaries when summary export is selected."))
    beast.add(JLabel("JMP graphs/histograms remain independent from Word report grouping."))
    fields["beast_max_total_runs"] = add_text_row(beast, "Maximum total ImageJ/JMP runs", DEFAULTS["beast_max_total_runs"], 20)
    fields["beast_checkpoint_every_runs"] = add_text_row(beast, "Rewrite checkpoint every N ImageJ runs", DEFAULTS["beast_checkpoint_every_runs"], 20)
    fields["beast_organize_windows_enabled"] = add_checkbox_row(beast, "Keep progress visible and tile Fiji/ImageJ windows", DEFAULTS["beast_organize_windows_enabled"])
    fields["beast_organize_jmp_windows_enabled"] = add_checkbox_row(beast, "Also move/tile JMP windows (OFF recommended)", DEFAULTS.get("beast_organize_jmp_windows_enabled", False))

    add_section(beast, "JMP worker safety")
    fields["beast_jmp_timeout_sec"] = add_text_row(beast, "Timeout per JMP run, seconds", DEFAULTS["beast_jmp_timeout_sec"], 20)
    fields["beast_jmp_exit_grace_sec"] = add_text_row(beast, "Grace after JMP_DONE before termination, seconds", DEFAULTS["beast_jmp_exit_grace_sec"], 20)
    fields["beast_jmp_launch_stagger_sec"] = add_text_row(beast, "Delay between worker launches, seconds", DEFAULTS["beast_jmp_launch_stagger_sec"], 20)
    fields["beast_jmp_retry_count"] = add_text_row(beast, "Automatic retries after a JMP crash/early exit", DEFAULTS.get("beast_jmp_retry_count", 1), 20)
    fields["beast_jmp_retry_delay_sec"] = add_text_row(beast, "Delay before a JMP retry, seconds", DEFAULTS.get("beast_jmp_retry_delay_sec", 6.0), 20)
    fields["beast_force_close_jmp_after_run"] = add_checkbox_row(beast, "Force-close each launched JMP process after its run", DEFAULTS["beast_force_close_jmp_after_run"])
    fields["beast_continue_on_imagej_error"] = add_checkbox_row(beast, "Continue queue after an ImageJ run error", DEFAULTS["beast_continue_on_imagej_error"])
    fields["beast_continue_on_jmp_error"] = add_checkbox_row(beast, "Continue queue after a JMP run error or timeout", DEFAULTS["beast_continue_on_jmp_error"])

    add_section(beast, "Automatic BEAST MODE changes")
    beast.add(JLabel("Default: JMP graphs/histograms are ON and the Word report mode is Combined Word report."))
    beast.add(JLabel("Choose No Word reports for XLSX/image output without DOCX generation."))
    beast.add(JLabel("Dynamic Fiji agents are visible by default; uncheck visibility for headless agents. Each process handles exactly one run, then exits; free slots pull from one shared queue."))
    beast.add(JLabel("Crash-resilient JMP mode keeps the configured parallel count, launches workers minimized, avoids JMP window tiling, and replaces only a worker that exits early."))
    beast.add(JLabel("JMP scripts receive Exit(NoSave). Each worker is monitored independently, retried after an early crash, and terminated after completion/timeout."))
    beast.add(JLabel("Final XLSX sheet 1 contains every detected pore in run order; sheet 2 contains ordered run timing/status/summary."))
    beast.add(JLabel("Persistent files: three-sheet BEAST XLSX, BEAST_MODE_Detailed_Log.csv, BEAST_MODE_Checkpoint.csv, and the run manifest."))


def pipeline_slot_prefix(slot_number):
    return "pipeline_%02d_" % int(slot_number)


def pipeline_component_value(component):
    try:
        if isinstance(component, JCheckBox):
            return bool(component.isSelected())
        if isinstance(component, JComboBox):
            return str(component.getSelectedItem())
        return str(component.getText())
    except:
        return None


def snapshot_pipeline_fields(fields):
    cache = fields.get("_pipeline_value_cache", {})
    for key in list(fields.keys()):
        if str(key).startswith("pipeline_") and not str(key).startswith("pipeline_order_"):
            value = pipeline_component_value(fields.get(key))
            if value is not None:
                cache[str(key)] = value
    fields["_pipeline_value_cache"] = cache
    return cache


def pipeline_cached_value(fields, key, fallback):
    cache = fields.get("_pipeline_value_cache", {})
    return cache.get(str(key), fallback)


def clear_dynamic_pipeline_field_keys(fields):
    for key in list(fields.keys()):
        if str(key).startswith("pipeline_") and not str(key).startswith("pipeline_order_") and key not in ["_pipeline_value_cache", "_pipeline_refresh_callback"]:
            try:
                del fields[key]
            except:
                pass
    for legacy_key in [
        "convert_8bit", "median_enabled", "median_radius", "contrast_enabled", "contrast_saturated", "contrast_normalize", "contrast_equalize",
        "bandpass_enabled", "bandpass_large", "bandpass_small", "bandpass_suppress", "bandpass_tolerance", "bandpass_autoscale", "bandpass_saturate",
        "clahe_enabled", "clahe_blocksize", "clahe_histogram", "clahe_maximum", "clahe_fast", "binary_enabled", "binary_fill_holes", "binary_watershed",
        "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations", "binary_erode_iterations", "binary_dilate_iterations",
        "binary_minimum_radius", "binary_maximum_radius", "binary_operation_order", "process_order"
    ]:
        if legacy_key in fields:
            try:
                del fields[legacy_key]
            except:
                pass


def attach_pipeline_listener(component, fields):
    callback = fields.get("_pipeline_refresh_callback")
    if callback is None or component is None:
        return
    try:
        if isinstance(component, JTextField):
            component.getDocument().addDocumentListener(SimpleDocListener(callback))
        else:
            component.addActionListener(callback)
    except:
        pass


def add_pipeline_checkbox(page, fields, key, label, fallback):
    comp = add_checkbox_row(page, label, bool(pipeline_cached_value(fields, key, fallback)))
    fields[key] = comp
    attach_pipeline_listener(comp, fields)
    return comp


def add_pipeline_text(page, fields, key, label, fallback, width=20):
    comp = add_text_row(page, label, pipeline_cached_value(fields, key, fallback), width)
    fields[key] = comp
    attach_pipeline_listener(comp, fields)
    return comp


def add_pipeline_combo(page, fields, key, label, choices, fallback):
    selected = pipeline_cached_value(fields, key, fallback)
    comp = add_combo_row(page, label, choices, selected)
    fields[key] = comp
    attach_pipeline_listener(comp, fields)
    return comp


def selected_pipeline_order_from_fields(fields):
    tokens = []
    combos = fields.get("_pipeline_order_combos", [])
    for combo in combos:
        try:
            label = str(combo.getSelectedItem())
            token = PROCESS_PIPELINE_LABEL_TO_TOKEN.get(label, "none")
        except:
            token = "none"
        tokens.append(token)
    return tokens


def build_dynamic_processing_page(proc, fields):
    snapshot_pipeline_fields(fields)
    clear_dynamic_pipeline_field_keys(fields)
    proc.removeAll()
    add_section(proc, "Ordered processing parameters")
    proc.add(JLabel("The numbered sections below come from ORDER. Duplicate operations have independent settings."))
    proc.add(JLabel("Threshold settings remain on Threshold + Analysis. Grayscale filters, including Minimum and Maximum, belong before Threshold; binary operations belong after it."))
    proc.add(Box.createVerticalStrut(8))

    first_alias = {}
    tokens = selected_pipeline_order_from_fields(fields)
    for slot_index, token in enumerate(tokens):
        if token == "none":
            continue
        slot_number = slot_index + 1
        prefix = pipeline_slot_prefix(slot_number)
        label = pipeline_operation_label(token)
        add_section(proc, ordinal_text(slot_number) + " - " + label)
        fields[prefix + "operation"] = token
        default_step = default_pipeline_step(token)

        if token == "threshold":
            proc.add(JLabel("Required phase boundary. Change threshold min/max and input mode on Threshold + Analysis."))
            fields[prefix + "enabled"] = True
            continue

        enabled = add_pipeline_checkbox(proc, fields, prefix + "enabled", "Enable this occurrence", default_step.get("enabled", True))
        if token == "median":
            add_pipeline_text(proc, fields, prefix + "radius", "Median radius", default_step.get("radius", 2.0))
        elif token == "contrast":
            add_pipeline_text(proc, fields, prefix + "saturated", "Saturated pixels", default_step.get("saturated", 0.35))
            add_pipeline_checkbox(proc, fields, prefix + "normalize", "Normalize", default_step.get("normalize", True))
            add_pipeline_checkbox(proc, fields, prefix + "equalize", "Equalize histogram", default_step.get("equalize", True))
        elif token == "bandpass":
            add_pipeline_text(proc, fields, prefix + "large", "Filter large structures down to", default_step.get("large", 40.0))
            add_pipeline_text(proc, fields, prefix + "small", "Filter small structures up to", default_step.get("small", 3.0))
            add_pipeline_combo(proc, fields, prefix + "suppress", "Suppress stripes", ["None", "Horizontal", "Vertical"], default_step.get("suppress", "None"))
            add_pipeline_text(proc, fields, prefix + "tolerance", "Tolerance", default_step.get("tolerance", 5.0))
            add_pipeline_checkbox(proc, fields, prefix + "autoscale", "Autoscale after filtering", default_step.get("autoscale", True))
            add_pipeline_checkbox(proc, fields, prefix + "saturate", "Saturate after filtering", default_step.get("saturate", False))
        elif token == "clahe":
            add_pipeline_text(proc, fields, prefix + "blocksize", "CLAHE block size", default_step.get("blocksize", 127))
            add_pipeline_text(proc, fields, prefix + "histogram", "CLAHE histogram bins", default_step.get("histogram", 256))
            add_pipeline_text(proc, fields, prefix + "maximum", "CLAHE maximum slope", default_step.get("maximum", 3.0))
            add_pipeline_checkbox(proc, fields, prefix + "fast", "CLAHE fast mode", default_step.get("fast", False))
        elif token in ["despeckle", "open", "close", "erode", "dilate"]:
            add_pipeline_text(proc, fields, prefix + "iterations", label + " iterations", default_step.get("iterations", 1))
        elif token in ["minimum", "maximum"]:
            add_pipeline_text(proc, fields, prefix + "radius", label + " radius (px)", default_step.get("radius", 1.0))
        elif token in ["fill_holes", "watershed", "8bit"]:
            proc.add(JLabel("This operation has no additional numeric parameters."))

        if token not in first_alias:
            first_alias[token] = prefix

    # Legacy aliases keep existing validation, summary, presets, and sweep code compatible.
    def alias(alias_name, token, suffix):
        prefix = first_alias.get(token)
        if prefix is not None and fields.get(prefix + suffix) is not None:
            fields[alias_name] = fields.get(prefix + suffix)

    alias("convert_8bit", "8bit", "enabled")
    alias("median_enabled", "median", "enabled"); alias("median_radius", "median", "radius")
    alias("contrast_enabled", "contrast", "enabled"); alias("contrast_saturated", "contrast", "saturated")
    alias("contrast_normalize", "contrast", "normalize"); alias("contrast_equalize", "contrast", "equalize")
    alias("bandpass_enabled", "bandpass", "enabled"); alias("bandpass_large", "bandpass", "large"); alias("bandpass_small", "bandpass", "small")
    alias("bandpass_suppress", "bandpass", "suppress"); alias("bandpass_tolerance", "bandpass", "tolerance")
    alias("bandpass_autoscale", "bandpass", "autoscale"); alias("bandpass_saturate", "bandpass", "saturate")
    alias("clahe_enabled", "clahe", "enabled"); alias("clahe_blocksize", "clahe", "blocksize"); alias("clahe_histogram", "clahe", "histogram")
    alias("clahe_maximum", "clahe", "maximum"); alias("clahe_fast", "clahe", "fast")
    alias("binary_fill_holes", "fill_holes", "enabled"); alias("binary_watershed", "watershed", "enabled")
    for token in ["despeckle", "open", "close", "erode", "dilate"]:
        alias("binary_" + token + "_iterations", token, "iterations")
    for token in ["minimum", "maximum"]:
        alias(token + "_filter_radius", token, "radius")
        alias("binary_" + token + "_radius", token, "radius")  # legacy alias
    binary_components = []
    for token in PROCESS_PIPELINE_BINARY_OPERATIONS:
        prefix = first_alias.get(token)
        if prefix is not None and fields.get(prefix + "enabled") is not None:
            binary_components.append(fields.get(prefix + "enabled"))
    fields["binary_enabled"] = binary_components[0] if len(binary_components) > 0 else None
    fields["process_order"] = None
    fields["binary_operation_order"] = None
    proc.add(Box.createVerticalStrut(8))
    proc.add(JLabel("Sweep values for a process type apply to every matching occurrence in this ordered pipeline."))
    proc.revalidate()
    proc.repaint()


def populate_v193_order_page(order_page, processing_page, fields):
    add_section(order_page, "ORDER - build the complete processing pipeline first")
    order_page.add(JLabel("Choose up to 20 numbered operations. The same operation may be selected more than once."))
    order_page.add(JLabel("Exactly one Threshold is required. Grayscale operations (including Minimum/Maximum) must be before it; binary operations must be after it."))
    order_page.add(JLabel("Example: choose Median as the 2nd and 5th steps, then set different radii for each on Processing."))
    order_page.add(Box.createVerticalStrut(8))
    labels = [label for token, label in PROCESS_PIPELINE_OPTIONS]
    default_tokens = str(DEFAULTS.get("process_pipeline_order", "8bit,median,contrast,bandpass,clahe,threshold")).split(",")
    combos = []

    def order_changed(event=None):
        if bool(fields.get("_quick_run_loading", False)):
            return
        try:
            source = event.getSource() if event is not None else None
            changed_index = combos.index(source) if source in combos else -1
            if changed_index >= 0:
                changed_prefix = pipeline_slot_prefix(changed_index + 1)
                cache = fields.get("_pipeline_value_cache", {})
                for cache_key in list(cache.keys()):
                    if str(cache_key).startswith(changed_prefix):
                        del cache[cache_key]
        except:
            pass
        build_dynamic_processing_page(processing_page, fields)
        callback = fields.get("_pipeline_refresh_callback")
        if callback is not None:
            try:
                callback()
            except:
                pass

    slot_count = int(DEFAULTS.get("process_pipeline_slot_count", 20))
    for index in range(slot_count):
        token = default_tokens[index].strip() if index < len(default_tokens) else "none"
        default_label = pipeline_operation_label(token)
        combo = add_combo_row(order_page, ordinal_text(index + 1) + " operation", labels, default_label)
        combo.addActionListener(order_changed)
        combos.append(combo)
        fields["pipeline_order_%02d" % (index + 1)] = combo
    fields["_pipeline_order_combos"] = combos
    fields["_pipeline_processing_panel"] = processing_page
    fields["_pipeline_value_cache"] = {}
    build_dynamic_processing_page(processing_page, fields)


def collect_pipeline_steps_from_fields(fields):
    snapshot_pipeline_fields(fields)
    steps = []
    tokens = selected_pipeline_order_from_fields(fields)
    for slot_index, token in enumerate(tokens):
        if token == "none":
            continue
        slot_number = slot_index + 1
        prefix = pipeline_slot_prefix(slot_number)
        label = pipeline_operation_label(token)
        step = default_pipeline_step(token)
        step["operation"] = token
        step["slot"] = slot_number
        if token == "threshold":
            step["enabled"] = True
        else:
            comp = fields.get(prefix + "enabled")
            step["enabled"] = bool(parse_bool_checkbox(comp)) if comp is not None else bool(step.get("enabled", True))
        def txt(name, fallback):
            comp2 = fields.get(prefix + name)
            if comp2 is None:
                return fallback
            return parse_text(comp2)
        def flt(name, label, fallback):
            comp2 = fields.get(prefix + name)
            if comp2 is None:
                return float(fallback)
            return parse_float_field(comp2, ordinal_text(slot_number) + " " + label)
        def integer(name, label, fallback):
            comp2 = fields.get(prefix + name)
            if comp2 is None:
                return int(fallback)
            return parse_int_field(comp2, ordinal_text(slot_number) + " " + label)
        if token in ["median", "minimum", "maximum"]:
            step["radius"] = max(0.0, flt("radius", label + " radius", step.get("radius", 0.0)))
        elif token == "contrast":
            step["saturated"] = max(0.0, flt("saturated", "contrast saturated pixels", step.get("saturated", 0.35)))
            step["normalize"] = parse_bool_checkbox(fields.get(prefix + "normalize"))
            step["equalize"] = parse_bool_checkbox(fields.get(prefix + "equalize"))
        elif token == "bandpass":
            step["large"] = max(0.0, flt("large", "bandpass large", step.get("large", 40.0)))
            step["small"] = max(0.0, flt("small", "bandpass small", step.get("small", 3.0)))
            step["suppress"] = str(fields.get(prefix + "suppress").getSelectedItem())
            step["tolerance"] = max(0.0, flt("tolerance", "bandpass tolerance", step.get("tolerance", 5.0)))
            step["autoscale"] = parse_bool_checkbox(fields.get(prefix + "autoscale"))
            step["saturate"] = parse_bool_checkbox(fields.get(prefix + "saturate"))
        elif token == "clahe":
            step["blocksize"] = max(1, integer("blocksize", "CLAHE block size", step.get("blocksize", 127)))
            step["histogram"] = max(2, integer("histogram", "CLAHE histogram bins", step.get("histogram", 256)))
            step["maximum"] = max(0.0, flt("maximum", "CLAHE maximum slope", step.get("maximum", 3.0)))
            step["fast"] = parse_bool_checkbox(fields.get(prefix + "fast"))
        elif token in ["despeckle", "open", "close", "erode", "dilate"]:
            step["iterations"] = max(0, integer("iterations", label + " iterations", step.get("iterations", 0)))
        steps.append(step)
    return validate_processing_pipeline_steps(steps)


def pipeline_gui_summary_from_fields(fields):
    bits = []
    for slot_index, token in enumerate(selected_pipeline_order_from_fields(fields)):
        if token == "none":
            continue
        prefix = pipeline_slot_prefix(slot_index + 1)
        enabled_comp = fields.get(prefix + "enabled")
        enabled = True if token == "threshold" or enabled_comp is None else bool(field_text_value(enabled_comp))
        suffix = "" if enabled else " (OFF)"
        if token in ["median", "minimum", "maximum"] and fields.get(prefix + "radius") is not None:
            suffix += " r=" + str(field_text_value(fields.get(prefix + "radius")))
        elif token in ["despeckle", "open", "close", "erode", "dilate"] and fields.get(prefix + "iterations") is not None:
            suffix += " x" + str(field_text_value(fields.get(prefix + "iterations")))
        bits.append(ordinal_text(slot_index + 1) + " " + pipeline_operation_label(token) + suffix)
    return " -> ".join(bits) if len(bits) > 0 else "None"


def populate_v193_threshold_page(thresh, fields):
    add_section(thresh, "Threshold")
    fields["threshold_min"] = add_text_row(thresh, "Threshold min", DEFAULTS["threshold_min"], 20)
    fields["threshold_max"] = add_text_row(thresh, "Threshold max", DEFAULTS["threshold_max"], 20)
    fields["black_background"] = add_checkbox_row(thresh, "Black background for binary conversion", DEFAULTS["black_background"])
    fields["threshold_force_8bit_numbers"] = add_checkbox_row(thresh, "Use 8-bit gray-value inputs (0-255); uncheck to use cumulative histogram percentiles (0-100%)", DEFAULTS["threshold_force_8bit_numbers"])
    thresh.add(JLabel("This input mode applies to normal thresholds, threshold sweeps, legacy auto-fit sweeps, and the +/-5 adjustment."))
    thresh.add(JLabel("Percent mode maps each requested percentile through the actual preprocessed-image histogram; reports show the resulting gray cutoffs."))
    thresh.add(Box.createVerticalStrut(6))

    add_section(thresh, "Auto scale unscaled images from red reference line")
    fields["auto_scale_unscaled_enabled"] = add_checkbox_row(thresh, "If image is unscaled, detect red reference line and set mm scale", DEFAULTS["auto_scale_unscaled_enabled"])
    fields["auto_scale_known_length_mm"] = add_text_row(thresh, "Known red reference line length, mm", DEFAULTS["auto_scale_known_length_mm"], 20)
    fields["auto_scale_min_component_pixels"] = add_text_row(thresh, "Minimum red-line component pixels", DEFAULTS["auto_scale_min_component_pixels"], 20)
    fields["auto_scale_show_preview"] = add_checkbox_row(thresh, "Show cropped preview of detected scale bar with traced line", DEFAULTS["auto_scale_show_preview"])
    fields["auto_scale_preview_padding_px"] = add_text_row(thresh, "Scale preview crop padding, pixels", DEFAULTS["auto_scale_preview_padding_px"], 20)
    thresh.add(JLabel("The popup shows detected pixel length, known length, mm/pixel, and pixels/mm before applying scale."))
    thresh.add(Box.createVerticalStrut(6))

    add_section(thresh, "Analyze Particles")
    fields["particle_size_min"] = add_text_row(thresh, "Particle size min", DEFAULTS["particle_size_min"], 20)
    fields["particle_size_max"] = add_text_row(thresh, "Particle size max", DEFAULTS["particle_size_max"], 20)
    fields["particle_circ_min"] = add_text_row(thresh, "Particle circularity min", DEFAULTS["particle_circ_min"], 20)
    fields["particle_circ_max"] = add_text_row(thresh, "Particle circularity max", DEFAULTS["particle_circ_max"], 20)
    fields["particle_include_holes"] = add_checkbox_row(thresh, "Analyze Particles: include holes", DEFAULTS["particle_include_holes"])
    fields["particle_exclude_edges"] = add_checkbox_row(thresh, "Analyze Particles: exclude particles touching image edges", DEFAULTS["particle_exclude_edges"])

    add_section(thresh, "Analyze Particles - Set Measurements")
    thresh.add(JLabel("Choose the ImageJ measurements written for every particle. Core workflow fields are automatically retained even if unchecked."))
    fields["measure_area"] = add_checkbox_row(thresh, "Area (core required)", DEFAULTS["measure_area"])
    fields["measure_mean"] = add_checkbox_row(thresh, "Mean gray value", DEFAULTS["measure_mean"])
    fields["measure_std_dev"] = add_checkbox_row(thresh, "Standard deviation", DEFAULTS["measure_std_dev"])
    fields["measure_mode"] = add_checkbox_row(thresh, "Modal gray value", DEFAULTS["measure_mode"])
    fields["measure_min_max"] = add_checkbox_row(thresh, "Minimum and maximum gray value", DEFAULTS["measure_min_max"])
    fields["measure_centroid"] = add_checkbox_row(thresh, "Centroid X/Y (core required)", DEFAULTS["measure_centroid"])
    fields["measure_center_of_mass"] = add_checkbox_row(thresh, "Center of mass XM/YM", DEFAULTS["measure_center_of_mass"])
    fields["measure_perimeter"] = add_checkbox_row(thresh, "Perimeter (core required)", DEFAULTS["measure_perimeter"])
    fields["measure_bounding_rect"] = add_checkbox_row(thresh, "Bounding rectangle", DEFAULTS["measure_bounding_rect"])
    fields["measure_fit_ellipse"] = add_checkbox_row(thresh, "Fit ellipse (core required)", DEFAULTS["measure_fit_ellipse"])
    fields["measure_shape_descriptors"] = add_checkbox_row(thresh, "Shape descriptors: circularity, aspect ratio, roundness, solidity (core required)", DEFAULTS["measure_shape_descriptors"])
    fields["measure_feret"] = add_checkbox_row(thresh, "Feret diameter", DEFAULTS["measure_feret"])
    fields["measure_integrated_density"] = add_checkbox_row(thresh, "Integrated density", DEFAULTS["measure_integrated_density"])
    fields["measure_median"] = add_checkbox_row(thresh, "Median gray value", DEFAULTS["measure_median"])
    fields["measure_skewness"] = add_checkbox_row(thresh, "Skewness", DEFAULTS["measure_skewness"])
    fields["measure_kurtosis"] = add_checkbox_row(thresh, "Kurtosis", DEFAULTS["measure_kurtosis"])
    fields["measure_area_fraction"] = add_checkbox_row(thresh, "Area fraction", DEFAULTS["measure_area_fraction"])
    fields["measure_stack_position"] = add_checkbox_row(thresh, "Stack position", DEFAULTS["measure_stack_position"])
    fields["measure_limit_to_threshold"] = add_checkbox_row(thresh, "Limit intensity measurements to threshold", DEFAULTS["measure_limit_to_threshold"])

    add_section(thresh, "JMP delete cutoff and automatic dependent limits")
    fields["epd_between_preset"] = add_combo_row(thresh, "Delete EPD preset", EPD_BETWEEN_PRESET_OPTIONS, DEFAULTS["epd_between_preset"])
    fields["small_epd_cutoff"] = add_text_row(thresh, "Delete EPD at or below, mm", DEFAULTS["small_epd_cutoff"], 20)
    fields["epd_between_low"] = add_text_row(thresh, "Between-count low, mm", DEFAULTS["epd_between_low"], 20)
    fields["epd_between_high"] = add_text_row(thresh, "Between-count high, mm", DEFAULTS["epd_between_high"], 20)
    thresh.add(JLabel("Select Delete at 3, 5, or 10 microns. The script then sets the between-count band to 3-5, 5-7, or 10-12 microns."))
    thresh.add(JLabel("The preset changes only the low-pore highlight: below 5, 7, or 12 microns. Pores above 25 microns are always highlighted. Choose Custom to edit the low limits."))
    fields["epd_cutoff_1"] = add_text_row(thresh, "Count epd(mm) above cutoff 1", DEFAULTS["epd_cutoff_1"], 20)
    fields["epd_cutoff_2"] = add_text_row(thresh, "Count epd(mm) above cutoff 2", DEFAULTS["epd_cutoff_2"], 20)

    def apply_epd_between_preset_fields(event=None):
        try:
            preset_name = str(fields["epd_between_preset"].getSelectedItem())
            if preset_name == "Custom":
                for key in ["small_epd_cutoff", "epd_between_low", "epd_between_high"]:
                    fields[key].setEditable(True)
                    fields[key].setBackground(Color.white)
            else:
                preset_low, preset_high, preset_source = resolve_epd_between_preset(preset_name, 0.0, 0.0)
                # The selected delete cutoff is the start of the active between band.
                fields["small_epd_cutoff"].setText(threshold_compact_number(preset_low))
                fields["epd_between_low"].setText(threshold_compact_number(preset_low))
                fields["epd_between_high"].setText(threshold_compact_number(preset_high))
                for key in ["small_epd_cutoff", "epd_between_low", "epd_between_high"]:
                    fields[key].setEditable(False)
                    fields[key].setBackground(Color(240, 240, 240))
        except:
            pass

    fields["epd_between_preset"].addActionListener(apply_epd_between_preset_fields)
    apply_epd_between_preset_fields()
    fields["circ_cutoff"] = add_text_row(thresh, "Count Circularity below", DEFAULTS["circ_cutoff"], 20)




def populate_v193_large_pore_repair_page(page, fields):
    add_section(page, "Large Pore Repair - conservative split correction")
    fields["large_pore_repair_enabled"] = add_checkbox_row(
        page,
        "Enable large-pore repair after thresholding (OFF by default)",
        DEFAULTS.get("large_pore_repair_enabled", False)
    )
    fields["large_pore_repair_mode"] = add_combo_row(
        page,
        "Approval mode",
        ["Review proposals", "Automatic conservative"],
        DEFAULTS.get("large_pore_repair_mode", "Review proposals")
    )
    page.add(JLabel("Required polarity: BLACK fibers / solid and WHITE pores. Repairs are small BLACK regions."))
    page.add(JLabel("The repair runs after threshold + ordered binary cleanup and before Analyze Particles."))
    page.add(JLabel("Review mode asks on the first threshold pass, then replays only approved locations after any threshold auto-fit reruns. BEAST/headless workers use automatic conservative mode."))

    add_section(page, "Large parent and child-pore safeguards")
    fields["large_pore_repair_min_parent_area_px"] = add_text_row(page, "Minimum large parent pore area, px", DEFAULTS.get("large_pore_repair_min_parent_area_px", 10000), 20)
    fields["large_pore_repair_largest_pore_limit"] = add_text_row(page, "Inspect only largest N qualifying pores", DEFAULTS.get("large_pore_repair_largest_pore_limit", 25), 20)
    fields["large_pore_repair_min_child_area_px"] = add_text_row(page, "Minimum child pore area after split, px", DEFAULTS.get("large_pore_repair_min_child_area_px", 2000), 20)
    fields["large_pore_repair_min_smaller_child_fraction"] = add_text_row(page, "Minimum smaller-child fraction of parent", DEFAULTS.get("large_pore_repair_min_smaller_child_fraction", 0.15), 20)
    fields["large_pore_repair_max_larger_child_fraction"] = add_text_row(page, "Maximum larger-child fraction of parent", DEFAULTS.get("large_pore_repair_max_larger_child_fraction", 0.85), 20)
    page.add(JLabel("A candidate is rejected unless one parent becomes exactly two substantial child pores with no extra fragments."))

    add_section(page, "Candidate search and repair-size limits")
    fields["large_pore_repair_min_closing_radius_px"] = add_text_row(page, "Minimum closing radius, px", DEFAULTS.get("large_pore_repair_min_closing_radius_px", 1), 20)
    fields["large_pore_repair_max_closing_radius_px"] = add_text_row(page, "Maximum closing radius, px", DEFAULTS.get("large_pore_repair_max_closing_radius_px", 10), 20)
    fields["large_pore_repair_radius_step_px"] = add_text_row(page, "Closing-radius step, px", DEFAULTS.get("large_pore_repair_radius_step_px", 1), 20)
    fields["large_pore_repair_min_area_px"] = add_text_row(page, "Minimum repair area, px", DEFAULTS.get("large_pore_repair_min_area_px", 2), 20)
    fields["large_pore_repair_max_area_px"] = add_text_row(page, "Maximum repair area, px", DEFAULTS.get("large_pore_repair_max_area_px", 150), 20)
    fields["large_pore_repair_max_fraction_of_parent"] = add_text_row(page, "Maximum repair fraction of parent", DEFAULTS.get("large_pore_repair_max_fraction_of_parent", 0.01), 20)
    fields["large_pore_repair_max_span_px"] = add_text_row(page, "Maximum repair bounding-box span, px", DEFAULTS.get("large_pore_repair_max_span_px", 25), 20)
    fields["large_pore_repair_crop_margin_px"] = add_text_row(page, "Extra crop margin around parent, px", DEFAULTS.get("large_pore_repair_crop_margin_px", 12), 20)
    fields["large_pore_repair_max_repairs_per_image"] = add_text_row(page, "Maximum accepted repairs per image", DEFAULTS.get("large_pore_repair_max_repairs_per_image", 5), 20)
    fields["large_pore_repair_include_edge_pores"] = add_checkbox_row(page, "Include large pores touching the image edge", DEFAULTS.get("large_pore_repair_include_edge_pores", False))

    add_section(page, "v193 Aggressive Largest-Pore Rescue")
    fields["large_pore_repair_largest_rescue_enabled"] = add_checkbox_row(
        page,
        "Run aggressive rescue on the largest pores",
        DEFAULTS.get("large_pore_repair_largest_rescue_enabled", True)
    )
    fields["large_pore_repair_largest_rescue_parent_limit"] = add_text_row(
        page, "Rescue only the largest N parent pores",
        DEFAULTS.get("large_pore_repair_largest_rescue_parent_limit", 5), 20
    )
    fields["large_pore_repair_largest_rescue_min_radius_px"] = add_text_row(
        page, "Rescue minimum closing radius, px",
        DEFAULTS.get("large_pore_repair_largest_rescue_min_radius_px", 4), 20
    )
    fields["large_pore_repair_largest_rescue_max_radius_px"] = add_text_row(
        page, "Rescue maximum closing radius, px",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_radius_px", 36), 20
    )
    fields["large_pore_repair_largest_rescue_max_area_px"] = add_text_row(
        page, "Rescue maximum repair area, px",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_area_px", 5000), 20
    )
    fields["large_pore_repair_largest_rescue_max_fraction_of_parent"] = add_text_row(
        page, "Rescue maximum repair fraction of parent",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_fraction_of_parent", 0.20), 20
    )
    fields["large_pore_repair_largest_rescue_max_span_px"] = add_text_row(
        page, "Rescue maximum repair span, px",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_span_px", 160), 20
    )
    fields["large_pore_repair_largest_rescue_min_smaller_child_fraction"] = add_text_row(
        page, "Rescue minimum smaller-child fraction",
        DEFAULTS.get("large_pore_repair_largest_rescue_min_smaller_child_fraction", 0.08), 20
    )
    fields["large_pore_repair_largest_rescue_max_larger_child_fraction"] = add_text_row(
        page, "Rescue maximum larger-child fraction",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_larger_child_fraction", 0.92), 20
    )
    fields["large_pore_repair_largest_rescue_max_repairs_per_image"] = add_text_row(
        page, "Maximum rescue repairs per image",
        DEFAULTS.get("large_pore_repair_largest_rescue_max_repairs_per_image", 2), 20
    )
    fields["large_pore_repair_force_largest_enabled"] = add_checkbox_row(
        page,
        "Force-test the single largest pore first using balanced-split ranking",
        DEFAULTS.get("large_pore_repair_force_largest_enabled", True)
    )
    fields["large_pore_repair_force_largest_max_radius_px"] = add_text_row(
        page, "Forced-largest maximum closing radius, px",
        DEFAULTS.get("large_pore_repair_force_largest_max_radius_px", 48), 20
    )
    fields["large_pore_repair_force_largest_max_area_px"] = add_text_row(
        page, "Forced-largest maximum repair area, px",
        DEFAULTS.get("large_pore_repair_force_largest_max_area_px", 8000), 20
    )
    fields["large_pore_repair_force_largest_max_fraction_of_parent"] = add_text_row(
        page, "Forced-largest maximum repair fraction",
        DEFAULTS.get("large_pore_repair_force_largest_max_fraction_of_parent", 0.30), 20
    )
    fields["large_pore_repair_force_largest_max_span_px"] = add_text_row(
        page, "Forced-largest maximum repair span, px",
        DEFAULTS.get("large_pore_repair_force_largest_max_span_px", 220), 20
    )
    fields["large_pore_repair_force_largest_min_child_area_px"] = add_text_row(
        page, "Forced-largest minimum child area, px",
        DEFAULTS.get("large_pore_repair_force_largest_min_child_area_px", 500), 20
    )
    fields["large_pore_repair_force_largest_min_smaller_child_fraction"] = add_text_row(
        page, "Forced-largest minimum smaller-child fraction",
        DEFAULTS.get("large_pore_repair_force_largest_min_smaller_child_fraction", 0.05), 20
    )
    fields["large_pore_repair_force_largest_max_larger_child_fraction"] = add_text_row(
        page, "Forced-largest maximum larger-child fraction",
        DEFAULTS.get("large_pore_repair_force_largest_max_larger_child_fraction", 0.95), 20
    )
    page.add(JLabel("v193 checks the single largest pore before all other repairs and ranks proposals by split balance rather than smallest bridge."))
    page.add(JLabel("It still requires exactly two child pores. Review mode remains recommended because this pass is intentionally aggressive."))

    add_section(page, "v193 Green-Target Multi-Neck Pass")
    fields["large_pore_repair_green_target_enabled"] = add_checkbox_row(
        page,
        "Recursively split medium pores at narrow necks",
        DEFAULTS.get("large_pore_repair_green_target_enabled", True)
    )
    fields["large_pore_repair_green_target_min_parent_area_px"] = add_text_row(
        page, "Green-target minimum parent area, px",
        DEFAULTS.get("large_pore_repair_green_target_min_parent_area_px", 2000), 20
    )
    fields["large_pore_repair_green_target_max_parent_area_px"] = add_text_row(
        page, "Green-target maximum parent area, px",
        DEFAULTS.get("large_pore_repair_green_target_max_parent_area_px", 18000), 20
    )
    fields["large_pore_repair_green_target_parent_limit"] = add_text_row(
        page, "Green-target initial parent limit",
        DEFAULTS.get("large_pore_repair_green_target_parent_limit", 180), 20
    )
    fields["large_pore_repair_green_target_min_radius_px"] = add_text_row(
        page, "Green-target minimum closing radius, px",
        DEFAULTS.get("large_pore_repair_green_target_min_radius_px", 2), 20
    )
    fields["large_pore_repair_green_target_max_radius_px"] = add_text_row(
        page, "Green-target maximum closing radius, px",
        DEFAULTS.get("large_pore_repair_green_target_max_radius_px", 10), 20
    )
    fields["large_pore_repair_green_target_min_area_px"] = add_text_row(
        page, "Green-target minimum repair area, px",
        DEFAULTS.get("large_pore_repair_green_target_min_area_px", 100), 20
    )
    fields["large_pore_repair_green_target_max_area_px"] = add_text_row(
        page, "Green-target maximum repair area, px",
        DEFAULTS.get("large_pore_repair_green_target_max_area_px", 2500), 20
    )
    fields["large_pore_repair_green_target_min_fraction_of_parent"] = add_text_row(
        page, "Green-target minimum repair fraction",
        DEFAULTS.get("large_pore_repair_green_target_min_fraction_of_parent", 0.02), 20
    )
    fields["large_pore_repair_green_target_max_fraction_of_parent"] = add_text_row(
        page, "Green-target maximum repair fraction",
        DEFAULTS.get("large_pore_repair_green_target_max_fraction_of_parent", 0.18), 20
    )
    fields["large_pore_repair_green_target_min_span_px"] = add_text_row(
        page, "Green-target minimum repair span, px",
        DEFAULTS.get("large_pore_repair_green_target_min_span_px", 18), 20
    )
    fields["large_pore_repair_green_target_max_span_px"] = add_text_row(
        page, "Green-target maximum repair span, px",
        DEFAULTS.get("large_pore_repair_green_target_max_span_px", 165), 20
    )
    fields["large_pore_repair_green_target_min_mean_thickness_px"] = add_text_row(
        page, "Green-target minimum mean repair thickness, px",
        DEFAULTS.get("large_pore_repair_green_target_min_mean_thickness_px", 2.5), 20
    )
    fields["large_pore_repair_green_target_max_mean_thickness_px"] = add_text_row(
        page, "Green-target maximum mean repair thickness, px",
        DEFAULTS.get("large_pore_repair_green_target_max_mean_thickness_px", 30.0), 20
    )
    fields["large_pore_repair_green_target_min_child_area_px"] = add_text_row(
        page, "Green-target minimum child area, px",
        DEFAULTS.get("large_pore_repair_green_target_min_child_area_px", 400), 20
    )
    fields["large_pore_repair_green_target_min_smaller_child_fraction"] = add_text_row(
        page, "Green-target minimum smaller-child fraction",
        DEFAULTS.get("large_pore_repair_green_target_min_smaller_child_fraction", 0.12), 20
    )
    fields["large_pore_repair_green_target_max_larger_child_fraction"] = add_text_row(
        page, "Green-target maximum larger-child fraction",
        DEFAULTS.get("large_pore_repair_green_target_max_larger_child_fraction", 0.82), 20
    )
    fields["large_pore_repair_green_target_max_repairs_per_image"] = add_text_row(
        page, "Maximum green-target repairs per image",
        DEFAULTS.get("large_pore_repair_green_target_max_repairs_per_image", 30), 20
    )
    fields["large_pore_repair_green_spur_enabled"] = add_checkbox_row(
        page,
        "Also show tiny-spur cut proposals",
        DEFAULTS.get("large_pore_repair_green_spur_enabled", True)
    )
    fields["large_pore_repair_green_spur_review_only"] = add_checkbox_row(
        page,
        "Tiny-spur cuts are review-only",
        DEFAULTS.get("large_pore_repair_green_spur_review_only", True)
    )
    fields["large_pore_repair_green_spur_max_repairs_per_image"] = add_text_row(
        page, "Maximum accepted tiny-spur cuts",
        DEFAULTS.get("large_pore_repair_green_spur_max_repairs_per_image", 5), 20
    )
    page.add(JLabel("This pass was tuned to the green annotations: parent areas about 2,000-18,000 px, radii 2-10 px, and longer narrow bridges."))
    page.add(JLabel("It is recursive: after one accepted cut, each resulting child is checked again so chained green corrections can be found."))
    page.add(JLabel("The master Large Pore Repair card remains OFF by default. Review mode is recommended for this aggressive pass."))

    add_section(page, "Fiber Fixer - fixed pre-sweep fiber network")
    fields["fiber_fixer_enabled"] = add_checkbox_row(
        page,
        "Enable Fiber Fixer before all sweep runs (OFF by default)",
        DEFAULTS.get("fiber_fixer_enabled", False)
    )
    fields["fiber_fixer_absolute_threshold_max"] = add_text_row(
        page, "Absolute dark-fiber threshold max (0-255)",
        DEFAULTS.get("fiber_fixer_absolute_threshold_max", 40), 20
    )
    fields["fiber_fixer_wire_width_px"] = add_text_row(
        page, "Final wireframe width, px",
        DEFAULTS.get("fiber_fixer_wire_width_px", 3), 20
    )
    fields["fiber_fixer_save_wireframe_mask"] = add_checkbox_row(
        page, "Save the complete black-on-white wireframe mask",
        DEFAULTS.get("fiber_fixer_save_wireframe_mask", True)
    )
    fields["fiber_fixer_save_preview_overlay"] = add_checkbox_row(
        page, "Save a red preview overlay before wireframe burn-in",
        DEFAULTS.get("fiber_fixer_save_preview_overlay", True)
    )
    page.add(JLabel("The mask is generated ONCE per selected image/crop before sweep combinations begin, using absolute threshold 0-40."))
    page.add(JLabel("All recovered fibers are skeletonized, expanded to 3 px, saved in the shared Fiber Fixer Masks folder, and reused for every higher-threshold run."))
    page.add(JLabel("Run order: fixed threshold-40 wireframe preparation -> each sweep threshold -> wireframe burn-in -> Large Pore Repair -> Analyze Particles."))

    add_section(page, "Display and saved outputs")
    fields["large_pore_repair_show_red_overlay"] = add_checkbox_row(page, "Keep accepted repairs visible as red overlays during review", DEFAULTS.get("large_pore_repair_show_red_overlay", True))
    fields["large_pore_repair_fill_red_overlay"] = add_checkbox_row(page, "Fill accepted red overlay regions", DEFAULTS.get("large_pore_repair_fill_red_overlay", False))
    fields["large_pore_repair_save_red_overlay_png"] = add_checkbox_row(page, "Save red repair overlay PNG in the run Images folder", DEFAULTS.get("large_pore_repair_save_red_overlay_png", True))
    fields["large_pore_repair_save_mask"] = add_checkbox_row(page, "Save standalone mostly-white repair mask", DEFAULTS.get("large_pore_repair_save_mask", False))
    fields["large_pore_repair_save_csv"] = add_checkbox_row(page, "Save accepted repair measurements CSV", DEFAULTS.get("large_pore_repair_save_csv", True))
    page.add(JLabel("The normal segmented output remains black/white. The separate repair mask is OFF by default to avoid an apparently blank white window."))

def populate_v193_auto_fit_page(fit, fields):
    add_section(fit, "Manual selected-pore +/-5 threshold adjustment")
    fields["auto_threshold_fit_enabled"] = add_checkbox_row(fit, "After manual selected pore, ask to accept or adjust threshold max by +/-5 selected units", DEFAULTS["auto_threshold_fit_enabled"])
    fields["auto_threshold_fit_apply_to_main"] = add_checkbox_row(fit, "Apply accepted +/-5 threshold changes to this run", DEFAULTS["auto_threshold_fit_apply_to_main"])
    fields["auto_threshold_fit_roi_count"] = add_text_row(fit, "Legacy traced-pore count; not used by +/-5 adjustment", DEFAULTS["auto_threshold_fit_roi_count"], 20)
    fields["auto_threshold_fit_trigger_percent_diff"] = add_text_row(fit, "Percent difference trigger for auto-fit/redo summary", DEFAULTS["auto_threshold_fit_trigger_percent_diff"], 20)
    fit.add(JLabel("Workflow: run threshold 40 first, manually select a pore, then only open the auto-fit/redo summary when the selected pore is outside the trigger percent."))
    fit.add(JLabel("Increasing threshold max increases pore area. +/-5 means gray levels in gray mode or percentage points in percent mode."))
    fit.add(Box.createVerticalStrut(6))

    add_section(fit, "Legacy sweep settings; not used by +/-5 adjustment")
    fields["auto_threshold_fit_sweep_min"] = add_checkbox_row(fit, "Sweep threshold min", DEFAULTS["auto_threshold_fit_sweep_min"])
    fields["auto_threshold_fit_min_start"] = add_text_row(fit, "Threshold min start", DEFAULTS["auto_threshold_fit_min_start"], 20)
    fields["auto_threshold_fit_min_end"] = add_text_row(fit, "Threshold min end", DEFAULTS["auto_threshold_fit_min_end"], 20)
    fields["auto_threshold_fit_min_step"] = add_text_row(fit, "Threshold min step", DEFAULTS["auto_threshold_fit_min_step"], 20)

    add_section(fit, "Threshold max sweep")
    fields["auto_threshold_fit_sweep_max"] = add_checkbox_row(fit, "Sweep threshold max", DEFAULTS["auto_threshold_fit_sweep_max"])
    fields["auto_threshold_fit_max_start"] = add_text_row(fit, "Threshold max start", DEFAULTS["auto_threshold_fit_max_start"], 20)
    fields["auto_threshold_fit_max_end"] = add_text_row(fit, "Threshold max end", DEFAULTS["auto_threshold_fit_max_end"], 20)
    fields["auto_threshold_fit_max_step"] = add_text_row(fit, "Threshold max step", DEFAULTS["auto_threshold_fit_max_step"], 20)

    add_section(fit, "Matching / output")
    fields["auto_threshold_fit_roi_padding"] = add_text_row(fit, "ROI neighborhood padding, pixels", DEFAULTS["auto_threshold_fit_roi_padding"], 20)
    fields["auto_threshold_fit_area_penalty"] = add_text_row(fit, "Area penalty weight", DEFAULTS["auto_threshold_fit_area_penalty"], 20)
    fields["auto_threshold_fit_max_tests"] = add_text_row(fit, "Maximum threshold combinations to test", DEFAULTS["auto_threshold_fit_max_tests"], 20)
    fields["auto_threshold_fit_save_csv"] = add_checkbox_row(fit, "Save fit sweep CSV", DEFAULTS["auto_threshold_fit_save_csv"])
    fields["auto_threshold_fit_save_best_mask"] = add_checkbox_row(fit, "Save best-fit mask image", DEFAULTS["auto_threshold_fit_save_best_mask"])
    fit.add(JLabel("Score = (1 - ROI overlap IoU) + area penalty * relative area error. Lower is better."))



def populate_v193_sweep_page(sweep, fields):
    add_section(sweep, "Sweep control")
    fields["sweep_enabled"] = add_checkbox_row(sweep, "Enable parameter sweep", DEFAULTS["sweep_enabled"])
    sweep.add(JLabel("Threshold min/max sweep fields use the same gray-value or percent input mode selected on Threshold + Analysis."))
    fields["sweep_all_listed"] = add_checkbox_row(sweep, "Sweep all listed parameters below", DEFAULTS["sweep_all_listed"])
    fields["max_sweep_runs"] = add_text_row(sweep, "Maximum sweep runs allowed", DEFAULTS["max_sweep_runs"], 20)

    add_section(sweep, "Sweep Until summary target")
    fields["sweep_until_enabled"] = add_checkbox_row(sweep, "Stop sweep when a summary target is reached", DEFAULTS["sweep_until_enabled"])
    fields["sweep_until_metric"] = add_combo_row(sweep, "Summary metric", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS["sweep_until_metric"])
    fields["sweep_until_operator"] = add_combo_row(sweep, "Stop condition", SWEEP_UNTIL_OPERATOR_OPTIONS, DEFAULTS["sweep_until_operator"])
    fields["sweep_until_target_value"] = add_text_row(sweep, "Target value; % symbol allowed", DEFAULTS["sweep_until_target_value"], 20)
    fields["sweep_until_equal_tolerance"] = add_text_row(sweep, "Equal-to tolerance", DEFAULTS["sweep_until_equal_tolerance"], 20)
    fields["sweep_until_stop_scope"] = add_combo_row(sweep, "When target is reached", SWEEP_UNTIL_STOP_SCOPE_OPTIONS, DEFAULTS["sweep_until_stop_scope"])
    sweep.add(JLabel("The stop test is calculated immediately from the ImageJ pore table and mirrors the final cleaned JMP summary."))
    sweep.add(JLabel("For multi-parameter sweeps, combinations are tested in the generated run order and stop at the first match."))

    add_section(sweep, "Threshold min sweep (selected threshold units)")
    fields["sweep_threshold_min"] = add_checkbox_row(sweep, "Sweep threshold min", DEFAULTS["sweep_threshold_min"])
    fields["sweep_threshold_min_start"] = add_text_row(sweep, "Threshold min start", DEFAULTS["sweep_threshold_min_start"], 20)
    fields["sweep_threshold_min_end"] = add_text_row(sweep, "Threshold min end", DEFAULTS["sweep_threshold_min_end"], 20)
    fields["sweep_threshold_min_step"] = add_text_row(sweep, "Threshold min step", DEFAULTS["sweep_threshold_min_step"], 20)

    add_section(sweep, "Threshold max sweep (selected threshold units)")
    fields["sweep_threshold_max"] = add_checkbox_row(sweep, "Sweep threshold max", DEFAULTS["sweep_threshold_max"])
    fields["sweep_threshold_max_start"] = add_text_row(sweep, "Threshold max start", DEFAULTS["sweep_threshold_max_start"], 20)
    fields["sweep_threshold_max_end"] = add_text_row(sweep, "Threshold max end", DEFAULTS["sweep_threshold_max_end"], 20)
    fields["sweep_threshold_max_step"] = add_text_row(sweep, "Threshold max step", DEFAULTS["sweep_threshold_max_step"], 20)

    add_section(sweep, "Enhance Contrast mode sweep")
    fields["sweep_contrast_enabled"] = add_checkbox_row(sweep, "Sweep selected Enhance Contrast modes", DEFAULTS["sweep_contrast_enabled"])
    sweep.add(JLabel("Choose any combination. Each selected mode creates one run per other sweep combination."))
    fields["sweep_contrast_mode_off"] = add_checkbox_row(sweep, "Include: Off", DEFAULTS["sweep_contrast_mode_off"])
    fields["sweep_contrast_mode_saturated"] = add_checkbox_row(sweep, "Include: Saturated cutoff only", DEFAULTS["sweep_contrast_mode_saturated"])
    fields["sweep_contrast_mode_normalize"] = add_checkbox_row(sweep, "Include: Normalize", DEFAULTS["sweep_contrast_mode_normalize"])
    fields["sweep_contrast_mode_equalize"] = add_checkbox_row(sweep, "Include: Equalize", DEFAULTS["sweep_contrast_mode_equalize"])
    sweep.add(JLabel("The Saturated pixels value from the ORDER contrast step is retained for every enabled mode."))

    add_section(sweep, "Median radius sweep")
    fields["sweep_median_radius"] = add_checkbox_row(sweep, "Sweep median radius", DEFAULTS["sweep_median_radius"])
    fields["sweep_median_radius_start"] = add_text_row(sweep, "Median radius start", DEFAULTS["sweep_median_radius_start"], 20)
    fields["sweep_median_radius_end"] = add_text_row(sweep, "Median radius end", DEFAULTS["sweep_median_radius_end"], 20)
    fields["sweep_median_radius_step"] = add_text_row(sweep, "Median radius step", DEFAULTS["sweep_median_radius_step"], 20)

    add_section(sweep, "Bandpass sweep")
    fields["sweep_bandpass_large"] = add_checkbox_row(sweep, "Sweep bandpass large value", DEFAULTS["sweep_bandpass_large"])
    fields["sweep_bandpass_large_start"] = add_text_row(sweep, "Bandpass large start", DEFAULTS["sweep_bandpass_large_start"], 20)
    fields["sweep_bandpass_large_end"] = add_text_row(sweep, "Bandpass large end", DEFAULTS["sweep_bandpass_large_end"], 20)
    fields["sweep_bandpass_large_step"] = add_text_row(sweep, "Bandpass large step", DEFAULTS["sweep_bandpass_large_step"], 20)

    fields["sweep_bandpass_small"] = add_checkbox_row(sweep, "Sweep bandpass small value", DEFAULTS["sweep_bandpass_small"])
    fields["sweep_bandpass_small_start"] = add_text_row(sweep, "Bandpass small start", DEFAULTS["sweep_bandpass_small_start"], 20)
    fields["sweep_bandpass_small_end"] = add_text_row(sweep, "Bandpass small end", DEFAULTS["sweep_bandpass_small_end"], 20)
    fields["sweep_bandpass_small_step"] = add_text_row(sweep, "Bandpass small step", DEFAULTS["sweep_bandpass_small_step"], 20)

    add_section(sweep, "CLAHE sweep")
    fields["sweep_clahe_blocksize"] = add_checkbox_row(sweep, "Sweep CLAHE block size", DEFAULTS["sweep_clahe_blocksize"])
    fields["sweep_clahe_blocksize_start"] = add_text_row(sweep, "CLAHE block size start", DEFAULTS["sweep_clahe_blocksize_start"], 20)
    fields["sweep_clahe_blocksize_end"] = add_text_row(sweep, "CLAHE block size end", DEFAULTS["sweep_clahe_blocksize_end"], 20)
    fields["sweep_clahe_blocksize_step"] = add_text_row(sweep, "CLAHE block size step", DEFAULTS["sweep_clahe_blocksize_step"], 20)

    fields["sweep_clahe_maximum"] = add_checkbox_row(sweep, "Sweep CLAHE maximum slope", DEFAULTS["sweep_clahe_maximum"])
    fields["sweep_clahe_maximum_start"] = add_text_row(sweep, "CLAHE maximum slope start", DEFAULTS["sweep_clahe_maximum_start"], 20)
    fields["sweep_clahe_maximum_end"] = add_text_row(sweep, "CLAHE maximum slope end", DEFAULTS["sweep_clahe_maximum_end"], 20)
    fields["sweep_clahe_maximum_step"] = add_text_row(sweep, "CLAHE maximum slope step", DEFAULTS["sweep_clahe_maximum_step"], 20)

    add_section(sweep, "Minimum / Maximum grayscale filter sweep")
    sweep.add(JLabel("These are grayscale filters and must appear before Threshold in ORDER. Repeated occurrences all receive the selected sweep value."))
    for key, label in [
        ("binary_minimum_radius", "Minimum filter radius (px)"),
        ("binary_maximum_radius", "Maximum filter radius (px)")
    ]:
        fields["sweep_" + key] = add_checkbox_row(sweep, "Sweep " + label, DEFAULTS["sweep_" + key])
        fields["sweep_" + key + "_start"] = add_text_row(sweep, label + " start", DEFAULTS["sweep_" + key + "_start"], 20)
        fields["sweep_" + key + "_end"] = add_text_row(sweep, label + " end", DEFAULTS["sweep_" + key + "_end"], 20)
        fields["sweep_" + key + "_step"] = add_text_row(sweep, label + " step", DEFAULTS["sweep_" + key + "_step"], 20)

    add_section(sweep, "Binary cleanup sweep")
    sweep.add(JLabel("For repeated ORDER operations, each selected sweep value is applied to every matching occurrence."))
    sweep.add(JLabel("Boolean ranges use 0=OFF and 1=ON. Iterations are whole numbers."))
    for key, label in [
        ("binary_enabled", "Binary cleanup enabled"),
        ("binary_fill_holes", "Fill holes"),
        ("binary_watershed", "Watershed"),
        ("binary_despeckle_iterations", "Despeckle iterations"),
        ("binary_open_iterations", "Open iterations"),
        ("binary_close_iterations", "Close iterations"),
        ("binary_erode_iterations", "Erode iterations"),
        ("binary_dilate_iterations", "Dilate iterations")
    ]:
        fields["sweep_" + key] = add_checkbox_row(sweep, "Sweep " + label, DEFAULTS["sweep_" + key])
        fields["sweep_" + key + "_start"] = add_text_row(sweep, label + " start", DEFAULTS["sweep_" + key + "_start"], 20)
        fields["sweep_" + key + "_end"] = add_text_row(sweep, label + " end", DEFAULTS["sweep_" + key + "_end"], 20)
        fields["sweep_" + key + "_step"] = add_text_row(sweep, label + " step", DEFAULTS["sweep_" + key + "_step"], 20)




def populate_v193_report_selection_page(selection_page, fields):
    add_section(selection_page, "Selected report for every image at every threshold")
    fields["threshold_selection_reports_enabled"] = add_checkbox_row(
        selection_page,
        "Create threshold-selected individual reports",
        DEFAULTS.get("threshold_selection_reports_enabled", False)
    )
    fields["threshold_selection_create_full_combined"] = add_checkbox_row(
        selection_page,
        "Also create one full combined Word report containing the entire batch",
        DEFAULTS.get("threshold_selection_create_full_combined", True)
    )
    fields["threshold_selection_folder_name"] = add_text_row(
        selection_page,
        "Selected individual-report folder name",
        DEFAULTS.get("threshold_selection_folder_name", "Selected_Threshold_Reports"),
        50
    )
    selection_page.add(JLabel("The script groups runs by image/crop + threshold min/max, then selects one run from each group."))
    selection_page.add(JLabel("The selected run is the median-radius/sweep result with the lowest weighted distance to the enabled targets."))
    selection_page.add(JLabel("Importance 1 = low; 5 = highest. Targets may include a % symbol for percentage metrics."))
    selection_page.add(JLabel("Example: 4 images x 5 thresholds x 3 median radii creates 20 selected individual reports."))

    add_section(selection_page, "Selection target 1")
    fields["threshold_selection_criterion_1_enabled"] = add_checkbox_row(selection_page, "Use target 1", DEFAULTS.get("threshold_selection_criterion_1_enabled", False))
    fields["threshold_selection_criterion_1_metric"] = add_combo_row(selection_page, "Summary-table data point", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS.get("threshold_selection_criterion_1_metric", "Area %"))
    fields["threshold_selection_criterion_1_target"] = add_text_row(selection_page, "Target value", DEFAULTS.get("threshold_selection_criterion_1_target", ""), 20)
    fields["threshold_selection_criterion_1_importance"] = add_text_row(selection_page, "Importance weight, 1-5", DEFAULTS.get("threshold_selection_criterion_1_importance", 1), 20)

    add_section(selection_page, "Selection target 2")
    fields["threshold_selection_criterion_2_enabled"] = add_checkbox_row(selection_page, "Use target 2", DEFAULTS.get("threshold_selection_criterion_2_enabled", False))
    fields["threshold_selection_criterion_2_metric"] = add_combo_row(selection_page, "Summary-table data point", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS.get("threshold_selection_criterion_2_metric", "Area %"))
    fields["threshold_selection_criterion_2_target"] = add_text_row(selection_page, "Target value", DEFAULTS.get("threshold_selection_criterion_2_target", ""), 20)
    fields["threshold_selection_criterion_2_importance"] = add_text_row(selection_page, "Importance weight, 1-5", DEFAULTS.get("threshold_selection_criterion_2_importance", 1), 20)

    add_section(selection_page, "Selection target 3")
    fields["threshold_selection_criterion_3_enabled"] = add_checkbox_row(selection_page, "Use target 3", DEFAULTS.get("threshold_selection_criterion_3_enabled", False))
    fields["threshold_selection_criterion_3_metric"] = add_combo_row(selection_page, "Summary-table data point", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS.get("threshold_selection_criterion_3_metric", "Area %"))
    fields["threshold_selection_criterion_3_target"] = add_text_row(selection_page, "Target value", DEFAULTS.get("threshold_selection_criterion_3_target", ""), 20)
    fields["threshold_selection_criterion_3_importance"] = add_text_row(selection_page, "Importance weight, 1-5", DEFAULTS.get("threshold_selection_criterion_3_importance", 1), 20)

    add_section(selection_page, "Selection target 4")
    fields["threshold_selection_criterion_4_enabled"] = add_checkbox_row(selection_page, "Use target 4", DEFAULTS.get("threshold_selection_criterion_4_enabled", False))
    fields["threshold_selection_criterion_4_metric"] = add_combo_row(selection_page, "Summary-table data point", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS.get("threshold_selection_criterion_4_metric", "Area %"))
    fields["threshold_selection_criterion_4_target"] = add_text_row(selection_page, "Target value", DEFAULTS.get("threshold_selection_criterion_4_target", ""), 20)
    fields["threshold_selection_criterion_4_importance"] = add_text_row(selection_page, "Importance weight, 1-5", DEFAULTS.get("threshold_selection_criterion_4_importance", 1), 20)

    add_section(selection_page, "Selection target 5")
    fields["threshold_selection_criterion_5_enabled"] = add_checkbox_row(selection_page, "Use target 5", DEFAULTS.get("threshold_selection_criterion_5_enabled", False))
    fields["threshold_selection_criterion_5_metric"] = add_combo_row(selection_page, "Summary-table data point", SWEEP_UNTIL_METRIC_OPTIONS, DEFAULTS.get("threshold_selection_criterion_5_metric", "Area %"))
    fields["threshold_selection_criterion_5_target"] = add_text_row(selection_page, "Target value", DEFAULTS.get("threshold_selection_criterion_5_target", ""), 20)
    fields["threshold_selection_criterion_5_importance"] = add_text_row(selection_page, "Importance weight, 1-5", DEFAULTS.get("threshold_selection_criterion_5_importance", 1), 20)

    add_section(selection_page, "Selection output details")
    selection_page.add(JLabel("The individual DOCX files contain only the selected image/run results."))
    selection_page.add(JLabel("Targets, importance weights, actual values, normalized distances, and weighted scores are written only to Threshold_Selection_Manifest.xls."))
    selection_page.add(JLabel("No selection criteria or scoring table is inserted into the Word reports."))

def populate_v209_report_recovery_page(recovery, fields):
    add_section(recovery, "Reports-only / failed-run recovery")
    fields["reports_only_recovery_mode"] = add_checkbox_row(
        recovery,
        "REPORTS ONLY: create/recreate reports without rerunning image processing",
        DEFAULTS.get("reports_only_recovery_mode", False)
    )
    fields["reports_only_source_mode"] = add_combo_row(
        recovery,
        "Reports-only source",
        [
            "Existing failed/incomplete output folder",
            "Existing generated Word report"
        ],
        DEFAULTS.get("reports_only_source_mode", "Existing failed/incomplete output folder")
    )
    fields["reports_only_output_mode"] = add_combo_row(
        recovery,
        "Reports-only Word output",
        [
            "Use normal Report card selection",
            "Combined Word report",
            "Individual by image",
            "Completely separate individual reports",
            "Individual by image + combined",
            "Completely separate individual reports + combined"
        ],
        DEFAULTS.get("reports_only_output_mode", "Use normal Report card selection")
    )
    recovery.add(JLabel("Existing output folder = recover completed runs from checkpoints/run folders and rebuild the selected report layout."))
    recovery.add(JLabel("Existing generated Word report = select a prior YOURE A BETA DOCX; the script finds its matching output root and can split it into separate reports."))
    recovery.add(JLabel("For splitting a combined report, choose Completely separate individual reports for one DOCX per run/permutation, or Individual by image for one DOCX per OG image."))
    recovery.add(JLabel("The original selected DOCX is never modified; split/recovered reports are written into a new folder under Word_Report."))

    add_section(recovery, "Always-on partial report recovery")
    recovery.add(JLabel("Report recovery state starts as soon as the output root exists and is updated as runs complete."))
    recovery.add(JLabel("If processing is stopped or crashes, the script keeps completed work and finishes the report/export phase instead of discarding it."))
    recovery.add(JLabel("If zero analysis runs completed, a minimal status DOCX is still attempted so the failed run leaves a report trail."))
    fields["always_finalize_partial_report"] = JCheckBox("Always finish a partial/status report after cancel or failure")
    fields["always_finalize_partial_report"].setSelected(True)
    try:
        fields["always_finalize_partial_report"].setEnabled(False)
    except:
        pass
    recovery.add(fields["always_finalize_partial_report"])

    add_section(recovery, "Batch live image report folders")
    fields["batch_live_image_report_folders_enabled"] = add_checkbox_row(
        recovery,
        "Batch mode: finish one image completely, live-fill its report folder, then move to the next image",
        DEFAULTS.get("batch_live_image_report_folders_enabled", False)
    )
    recovery.add(JLabel("Example: 6 images x 5 runs = finish all 5 runs for Image 1, write its 5 run reports, show Image 1 of 6 complete, then start Image 2."))
    recovery.add(JLabel("With BEAST MODE, Fiji agents stay parallel INSIDE the current image, but the next image is held until the current image and its live reports are complete."))
    recovery.add(JLabel("At the end, enabled combined output is written to Word_Report/Batch_Final/Combined_Report and enabled summaries are collected in Word_Report/Batch_Final/Summaries."))

    add_section(recovery, "Excel summaries + manual collection")
    fields["export_main_summary_xls"] = add_checkbox_row(
        recovery,
        "Save simple main-summary-only Excel .xls using the Word report name + _summaries",
        DEFAULTS["export_main_summary_xls"]
    )
    fields["batch_sweep_export_all_summaries_to_all_reports"] = add_checkbox_row(
        recovery,
        "Batch sweep summaries: copy every report summary to all available All Reports folders",
        DEFAULTS["batch_sweep_export_all_summaries_to_all_reports"]
    )
    recovery.add(JLabel("This summary mirror remains independent of Combined / by-image / completely-individual Word report creation."))
    fields["summary_xls_destination"] = add_combo_row(
        recovery,
        "Excel summary destination",
        [
            "Project Reports folder",
            "All configured report destinations",
            "Run output folder",
            "Custom folder",
            "Manual selection at end"
        ],
        DEFAULTS["summary_xls_destination"]
    )
    fields["summary_xls_custom_folder"] = add_text_row(
        recovery, "Custom Excel summary folder", DEFAULTS["summary_xls_custom_folder"], 60
    )
    recovery.add(JLabel("Manual selection at end = stage summaries first, inspect the available files in a dropdown, then copy the selected summary or all summaries into a NEW folder."))
    recovery.add(JLabel("This manual-copy step is available for normal runs and reports-only recovery runs."))
    recovery.add(JLabel("Auto-detect checks both configured All Reports locations and falls back to Word_Report."))

def populate_v193_report_page(report, fields):
    add_section(report, "Word report creation")
    # The six-mode dropdown is authoritative in v193. Keep a hidden legacy
    # checkbox so old presets and helper code can still read create_word_report.
    fields["create_word_report"] = JCheckBox("Legacy create Word report")
    fields["create_word_report"].setSelected(str(DEFAULTS.get("word_report_mode", "Combined Word report")) != "No Word reports")
    report_modes = list(DEFAULTS.get("word_report_mode_options", ["No Word reports", "Combined Word report", "Individual by image", "Completely separate individual reports", "Individual by image + combined", "Completely separate individual reports + combined"]))
    report_mode_default = str(DEFAULTS.get("word_report_mode", "Combined Word report"))
    if report_mode_default not in report_modes:
        report_modes.append(report_mode_default)
    fields["word_report_mode"] = add_combo_row(report, "Word report output (Normal + BEAST MODE)", report_modes, report_mode_default)
    report.add(JLabel("Individual by image = one DOCX per original input image containing all of its crops/sweeps."))
    report.add(JLabel("Completely separate individual reports = one DOCX for every processed run/crop/sweep result."))
    report.add(JLabel("This ONE dropdown controls Normal + BEAST MODE. Completely individual = exactly one DOCX per completed run/permutation under Word_Report/Completely_Individual_Reports."))
    report.add(JLabel("If Excel summaries are selected, every generated report also gets its own matching *_summaries.xls; BEAST additionally keeps its master workbook."))
    fields["open_word_report_when_done"] = add_checkbox_row(report, "Open Word DOCX report(s) when finished (legacy; OFF by default)", DEFAULTS["open_word_report_when_done"])

    add_section(report, "Threshold-selected reports")
    report.add(JLabel("Selection settings have moved to the separate Report Selection card immediately after this Report card."))

    add_section(report, "Report file name")
    fields["report_filename_mode"] = add_combo_row(
        report,
        "Report naming mode",
        ["Auto name: image + processing steps", "Ask me for report name after processing"],
        DEFAULTS["report_filename_mode"]
    )
    report.add(JLabel("Automatic names include the image name and basic enabled processing/sweep steps."))

    add_section(report, "Summary export + recovery tools")
    report.add(JLabel("Excel summary collection and all reports-only/recovery tools have moved to the new Report Recovery + Summaries card."))

    add_section(report, "Lossless / space-saving image handling")
    report.add(JLabel("All options are OFF by default, which keeps the existing full-lossless PNG/TIFF workflow."))
    fields["no_lossless_images_in_reports"] = add_checkbox_row(report, "No lossless images in Word reports (embed temporary JPEG copies)", DEFAULTS.get("no_lossless_images_in_reports", False))
    fields["dont_save_lossless_generated_images"] = add_checkbox_row(report, "Do not retain lossless generated run images (replace generated PNG/TIFF with JPEG after exports)", DEFAULTS.get("dont_save_lossless_generated_images", False))
    fields["no_lossless_images_at_all"] = add_checkbox_row(report, "No lossless generated/report visuals at all (master override; enables both options above)", DEFAULTS.get("no_lossless_images_at_all", False))
    report.add(JLabel("These settings do NOT alter thresholding/EPD calculations and do NOT compress calibrated analysis-source TIFFs (capture, Scaled image, or crop inputs)."))
    report.add(JLabel("The generated-image option also skips several redundant per-run TIFF writes and removes remaining PNG/TIFF visualization copies after reports/XLSX are complete."))
    def sync_no_lossless_master(event=None):
        try:
            if fields["no_lossless_images_at_all"].isSelected():
                fields["no_lossless_images_in_reports"].setSelected(True)
                fields["dont_save_lossless_generated_images"].setSelected(True)
        except:
            pass
    try:
        fields["no_lossless_images_at_all"].addActionListener(sync_no_lossless_master)
    except:
        pass
    sync_no_lossless_master()
    report.add(Box.createVerticalStrut(6))
    fields["report_launch_all_jmp"] = add_checkbox_row(report, "For report: launch every generated JMP script", DEFAULTS["report_launch_all_jmp"])
    fields["report_wait_for_jmp"] = add_checkbox_row(report, "For report: wait for JMP summaries/histograms before building DOCX", DEFAULTS["report_wait_for_jmp"])
    fields["report_wait_timeout_sec"] = add_text_row(report, "JMP wait timeout per report batch, seconds", DEFAULTS["report_wait_timeout_sec"], 20)

    add_section(report, "Report labels")
    fields["report_title"] = add_text_row(report, "Report title", DEFAULTS["report_title"], 60)
    fields["report_sample_name"] = add_text_row(report, "Sample used label, blank = image name", DEFAULTS["report_sample_name"], 60)
    scale_method_options = list(DEFAULTS.get("report_scale_method_options", ["Needle scale", "Old Plastic", "New Glass"]))
    scale_method_default = str(DEFAULTS.get("report_scale_method", "Needle scale"))
    if scale_method_default not in scale_method_options:
        scale_method_options.append(scale_method_default)
    fields["report_scale_method"] = add_combo_row(report, "How scale was set", scale_method_options, scale_method_default)
    report.add(JLabel("Add or rename scale choices in Defaults and Other Stuff/GDL_User_Defaults.py under report_scale_method_options."))
    imaging_software_options = list(DEFAULTS.get("report_imaging_software_options", ["Swift Imaging 3.0"]))
    imaging_software_default = str(DEFAULTS.get("report_imaging_software", "Swift Imaging 3.0"))
    if imaging_software_default not in imaging_software_options:
        imaging_software_options.append(imaging_software_default)
    fields["report_imaging_software"] = add_combo_row(report, "Imaging software", imaging_software_options, imaging_software_default)
    report.add(JLabel("Add or rename imaging-software choices in GDL_User_Defaults.py under report_imaging_software_options."))

    add_section(report, "Report image sizing")
    fields["report_main_image_width_in"] = add_text_row(report, "Each main image width, inches; 3 images are placed side-by-side", DEFAULTS["report_main_image_width_in"], 20)
    fields["report_hist_image_width_in"] = add_text_row(report, "Histogram image width, inches", DEFAULTS["report_hist_image_width_in"], 20)
    fields["report_pore_map_width_in"] = add_text_row(report, "Pore map image width, inches", DEFAULTS["report_pore_map_width_in"], 20)

    add_section(report, "Strand heat map")
    report.add(JLabel("Creates ONE rainbow brightness visualization per original image before preprocessing/segmentation."))
    report.add(JLabel("Darkest intensity = purple; brightest intensity = red; the colors scale through the full rainbow in between."))
    fields["report_include_strand_heat_map"] = add_checkbox_row(report, "Include one pre-segmentation rainbow heat map per original image in every Word report", DEFAULTS.get("report_include_strand_heat_map", True))
    fields["report_save_strand_heat_map"] = add_checkbox_row(report, "Save strand rainbow heat map PNG in the Images folder", DEFAULTS.get("report_save_strand_heat_map", True))

    add_section(report, "DOCX page size")
    fields["docx_body_page_width_in"] = add_text_row(report, "Entire report/body page width, inches", DEFAULTS["docx_body_page_width_in"], 20)
    fields["docx_body_page_height_in"] = add_text_row(report, "Entire report/body page height, inches", DEFAULTS["docx_body_page_height_in"], 20)
    fields["docx_body_margin_in"] = add_text_row(report, "Entire report/body page margin, inches", DEFAULTS["docx_body_margin_in"], 20)
    fields["docx_summary_page_width_in"] = add_text_row(report, "End summary page width, inches", DEFAULTS["docx_summary_page_width_in"], 20)
    fields["docx_summary_page_height_in"] = add_text_row(report, "End summary page height, inches", DEFAULTS["docx_summary_page_height_in"], 20)
    fields["docx_summary_margin_in"] = add_text_row(report, "End summary page margin, inches", DEFAULTS["docx_summary_margin_in"], 20)

    fields["report_sweep_comparison_enabled"] = add_checkbox_row(report, "Add side-by-side sweep/batch comparison image page", DEFAULTS["report_sweep_comparison_enabled"])
    # Legacy field retained invisibly for old presets. The six-mode dropdown above
    # now controls all grouping behavior directly.
    fields["batch_sweep_reports_by_og_image"] = JCheckBox("Legacy batch sweep reports by OG image")
    fields["batch_sweep_reports_by_og_image"].setSelected(True)
    report.add(JLabel("Batch/Excel summary destination controls are on the Report Recovery + Summaries card."))

    add_section(report, "Segmented image overlays")
    fields["highlight_largest_pore_in_segmented"] = add_checkbox_row(report, "Highlight the largest pore on each segmented image", DEFAULTS["highlight_largest_pore_in_segmented"])
    fields["report_save_segmented_overlay_next_to_word"] = add_checkbox_row(report, "Save segmented overlay PNGs in the Images folder", DEFAULTS["report_save_segmented_overlay_next_to_word"])
    fields["report_segmented_overlay_fiber_color"] = add_combo_row(report, "Segmented overlay fiber color", COLOR_NAME_OPTIONS, DEFAULTS["report_segmented_overlay_fiber_color"])
    fields["report_segmented_overlay_fiber_opacity_percent"] = add_text_row(report, "Segmented overlay fiber opacity (%)", DEFAULTS["report_segmented_overlay_fiber_opacity_percent"], 20)
    fields["report_segmented_overlay_annotation_opacity_percent"] = add_text_row(report, "Segmented overlay annotation opacity (%)", DEFAULTS["report_segmented_overlay_annotation_opacity_percent"], 20)
    fields["report_segmented_pores_overlay_opacity_percent"] = add_text_row(report, "Segmented black/white overlay opacity (%)", DEFAULTS["report_segmented_pores_overlay_opacity_percent"], 20)
    fields["save_fiji_log_enabled"] = add_checkbox_row(report, "Save Fiji/ImageJ log as Fiji_Log.txt in output folder", DEFAULTS["save_fiji_log_enabled"])
    # v89 merged manual pore workflow: keep the legacy largest-pore fields hidden/off so the startup choices
    # show one manual trace option instead of separate largest-pore and user-pore workflows.
    fields["manual_largest_pore_enabled"] = JCheckBox("Legacy separate largest-pore manual measurement")
    fields["manual_largest_pore_enabled"].setSelected(False)
    fields["manual_largest_pore_count"] = JTextField("0", 20)
    fields["manual_selected_pore_enabled"] = add_checkbox_row(report, "Manual pore trace: show largest-pore guide, then trace largest or any pore", DEFAULTS["manual_selected_pore_enabled"])
    fields["manual_selected_pore_count"] = add_text_row(report, "Manual pore trace count", DEFAULTS["manual_selected_pore_count"], 20)
    fields["manual_success_popup_show_picture"] = add_checkbox_row(report, "Show picture in under-5% success popup", DEFAULTS["manual_success_popup_show_picture"])
    fields["manual_strand_measurement_enabled"] = add_checkbox_row(report, "Manual strand measurement: select one strand once per original batch image", DEFAULTS["manual_strand_measurement_enabled"])
    report.add(JLabel("The accepted strand measurement is reused for every sweep/run of that same original image."))

    add_section(report, "Custom overlay styles")
    fields["guide_largest_outline_color"] = add_combo_row(report, "Guide image largest-pore outline color", COLOR_NAME_OPTIONS, DEFAULTS["guide_largest_outline_color"])
    fields["guide_selected_outline_color"] = add_combo_row(report, "Guide image selected-pore outline color", COLOR_NAME_OPTIONS, DEFAULTS["guide_selected_outline_color"])
    fields["guide_outline_extra_pixels"] = add_text_row(report, "Guide outline outward offset, pixels", DEFAULTS["guide_outline_extra_pixels"], 20)
    fields["guide_outline_line_width"] = add_text_row(report, "Guide outline line width", DEFAULTS["guide_outline_line_width"], 20)
    fields["segmented_largest_fill_color"] = add_combo_row(report, "Segmented largest-pore fill color", COLOR_NAME_OPTIONS, DEFAULTS["segmented_largest_fill_color"])
    fields["segmented_selected_fill_color"] = add_combo_row(report, "Segmented selected-pore fill color", COLOR_NAME_OPTIONS, DEFAULTS["segmented_selected_fill_color"])
    fields["segmented_outline_line_width"] = add_text_row(report, "Segmented label/backup line width", DEFAULTS["segmented_outline_line_width"], 20)

    add_section(report, "Pore map overlays")
    report.add(JLabel("The main map highlights low pores below the preset upper limit and always highlights pores above 25 microns."))
    fields["report_pore_map_low_marker_radius"] = add_text_row(report, "Small-pore marker radius, pixels", DEFAULTS["report_pore_map_low_marker_radius"], 20)
    fields["report_pore_map_high_marker_radius"] = add_text_row(report, "Large-pore marker radius, pixels", DEFAULTS["report_pore_map_high_marker_radius"], 20)
    fields["report_pore_map_opacity_percent"] = add_text_row(report, "Pore-map marker opacity, %", DEFAULTS["report_pore_map_opacity_percent"], 20)
    fields["report_pore_map_background"] = add_combo_row(report, "Pore map background", ["Original image", "Segmented mask", "White background"], DEFAULTS["report_pore_map_background"])
    fields["pore_map_low_color"] = add_combo_row(report, "Low pores below selected limit color", COLOR_NAME_OPTIONS, DEFAULTS["pore_map_low_color"])
    report.add(JLabel("High pores above 25 microns are always shown in red; the delete preset does not change them."))
    fields["report_pore_map_show_legend"] = add_checkbox_row(report, "Draw legend text on pore map image", DEFAULTS["report_pore_map_show_legend"])
    fields["report_all_pore_map_enabled"] = add_checkbox_row(report, "Add second all-pore centroid EPD map", DEFAULTS["report_all_pore_map_enabled"])
    fields["report_all_pore_map_style"] = add_combo_row(report, "Second all-pore map style", ["EPD-sized grayscale markers", "EPD-sized red markers on white", "Fixed 6 px red hue by EPD"], DEFAULTS["report_all_pore_map_style"])
    fields["report_all_pore_map_show_legend"] = add_checkbox_row(report, "Draw legend text on second all-pore map", DEFAULTS["report_all_pore_map_show_legend"])

    add_section(report, "Scale bar")
    fields["report_scale_bar_enabled"] = add_checkbox_row(report, "Add scale bar to report images (forced ON)", True)
    fields["report_scale_bar_auto_fit_enabled"] = add_checkbox_row(report, "Use auto-fit scale bar: 1/5 image width, nearest 50 microns", DEFAULTS["report_scale_bar_auto_fit_enabled"])
    fields["report_scale_bar_length_mm"] = add_text_row(report, "Normal fixed scale bar length [mm]", DEFAULTS["report_scale_bar_length_mm"], 20)
    fields["report_scale_bar_thickness_px"] = add_text_row(report, "Scale bar thickness, pixels", DEFAULTS["report_scale_bar_thickness_px"], 20)
    fields["report_scale_bar_margin_px"] = add_text_row(report, "Scale bar edge margin, pixels", DEFAULTS["report_scale_bar_margin_px"], 20)
    fields["report_scale_bar_color"] = add_combo_row(report, "Scale bar color", COLOR_NAME_OPTIONS, DEFAULTS["report_scale_bar_color"])
    fields["report_scale_bar_label_enabled"] = add_checkbox_row(report, "Draw scale bar label text", DEFAULTS["report_scale_bar_label_enabled"])
    fields["report_scale_bar_text_color"] = add_combo_row(report, "Scale bar label text color", COLOR_NAME_OPTIONS, DEFAULTS["report_scale_bar_text_color"])
    fields["report_scale_bar_text_outline_enabled"] = add_checkbox_row(report, "Draw scale bar label text outline", DEFAULTS["report_scale_bar_text_outline_enabled"])
    fields["report_scale_bar_text_outline_color"] = add_combo_row(report, "Scale bar label outline color", COLOR_NAME_OPTIONS, DEFAULTS["report_scale_bar_text_outline_color"])
    fields["report_scale_bar_font_size_px"] = add_text_row(report, "Scale bar label font size, pixels", DEFAULTS["report_scale_bar_font_size_px"], 20)

    add_section(report, "Quality checks")
    fields["bad_image_detection_enabled"] = add_checkbox_row(report, "Run bad-image detection and add warnings to report", DEFAULTS["bad_image_detection_enabled"])
    fields["popup_warning_summary_enabled"] = add_checkbox_row(report, "Show end-of-run warning summary popup", DEFAULTS["popup_warning_summary_enabled"])
    fields["scale_sanity_warning_enabled"] = add_checkbox_row(report, "Scale sanity checker: warn about suspicious mm scale", DEFAULTS["scale_sanity_warning_enabled"])
    fields["scale_sanity_min_image_area_mm2"] = add_text_row(report, "Scale sanity: minimum image area, mm^2", DEFAULTS["scale_sanity_min_image_area_mm2"], 20)
    fields["scale_sanity_max_image_area_mm2"] = add_text_row(report, "Scale sanity: maximum image area, mm^2", DEFAULTS["scale_sanity_max_image_area_mm2"], 20)
    fields["scale_sanity_min_pixel_size_mm"] = add_text_row(report, "Scale sanity: minimum pixel size, mm/pixel", DEFAULTS["scale_sanity_min_pixel_size_mm"], 20)
    fields["scale_sanity_max_pixel_size_mm"] = add_text_row(report, "Scale sanity: maximum pixel size, mm/pixel", DEFAULTS["scale_sanity_max_pixel_size_mm"], 20)
    fields["particle_count_sanity_enabled"] = add_checkbox_row(report, "Particle-count sanity checker", DEFAULTS["particle_count_sanity_enabled"])
    fields["particle_count_high_limit"] = add_text_row(report, "Warn if particle count is above", DEFAULTS["particle_count_high_limit"], 20)
    fields["particle_count_change_warning_percent"] = add_text_row(report, "Warn if particle count changes by more than, %", DEFAULTS["particle_count_change_warning_percent"], 20)
