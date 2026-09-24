import Section from '../components/Section'
import SetupChecklist from '../components/SetupChecklist'
import ThresholdsEditor from '../components/ThresholdsEditor'
import ModelsSection from '../components/ModelsSection'

/** Page 3 — Settings (SPEC §17). One page, collapsible sections with anchors so
 *  the Prompt page can deep-link (e.g. /settings#zones?camera=CAM_01&name=desk). */
export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Everything the system needs, in one page. Sections for phases that are not
          built yet say so.
        </p>
      </div>

      <SetupChecklist />

      <Section
        id="cameras"
        title="Cameras"
        description="Webcam, video file or RTSP sources."
        availableAfterPhase={1}
      />
      <Section
        id="zones"
        title="Zones"
        description="Draw named polygons on a snapshot."
        availableAfterPhase={2}
      />
      <Section
        id="calibration"
        title="Calibration"
        description="4-point floor calibration for distances in metres."
        availableAfterPhase={3}
      />
      <Section
        id="anchors"
        title="Anchors"
        description="Static objects found by text prompt (open-vocabulary)."
        availableAfterPhase={5}
      />
      <Section
        id="concepts"
        title="Visual concepts"
        description="Teach an object from 3–5 reference images."
        availableAfterPhase={6}
      />

      <Section
        id="models"
        title="Models"
        description="What is loaded, on which device, and what is missing."
      >
        <ModelsSection />
      </Section>

      <Section
        id="thresholds"
        title="Thresholds"
        description="Runtime-editable values. Saved values persist across a backend restart."
      >
        <ThresholdsEditor />
      </Section>

      <Section
        id="learning"
        title="Learning"
        description="Learning queue, unknown-object candidates and parser examples."
        availableAfterPhase={8}
      />
    </div>
  )
}
