using System.Collections;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering;

// 브라우저 계약: GameObject 'ShipViewer', SetView(front|side|top|reset), 첫 렌더 뒤 shipviewer-ready 1회.
public class ShipViewer : MonoBehaviour
{
    public Camera cam;
    public Material[] materials;

    const float K = 12f;
    const float PitchMin = 4f, PitchMax = 88f, DistMin = 50f, DistMax = 540f;
    static readonly Vector3 DefaultPivot = new Vector3(0f, 7f, 0f);

    float yaw, pitch, dist; Vector3 pivot;          // 현재값
    float tYaw, tPitch, tDist; Vector3 tPivot;     // 목표값
    Vector3 lastMouse;
    Transform ship;
    bool hovering;
    Transform singleYard, fleetYard;
    Transform[] fleet;
    Transform crane;
    Vector3 press;
    int hoveredSlot = -1;
    int pressedSlot = -1;
    float lastAspect;
    string fleetView = "reset";

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ShipViewer_NotifyReady();
    [DllImport("__Internal")] static extern void ShipViewer_NotifyHover(int active);
    [DllImport("__Internal")] static extern void ShipViewer_FleetEvent(int slot, int selected);
#else
    static void ShipViewer_NotifyReady() { }
    static void ShipViewer_NotifyHover(int active) { }
    static void ShipViewer_FleetEvent(int slot, int selected) { }
#endif

    void Awake()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = false;
#endif
        Application.runInBackground = true;
        QualitySettings.shadows = ShadowQuality.All;
        QualitySettings.shadowDistance = 400f;
        QualitySettings.shadowResolution = ShadowResolution.VeryHigh;
        QualitySettings.shadowCascades = 1;
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);
        if (cam == null) cam = Camera.main;
        singleYard = ShipModel.BuildYard(materials);
        ship = ShipModel.Build(materials).transform;
    }

    IEnumerator Start()
    {
        Apply("reset", true);
        yield return new WaitForEndOfFrame();
        ShipViewer_NotifyReady();
    }

    public void SetView(string view) => Apply(view, false);

    public void SetFleet(string count)
    {
        if (!int.TryParse(count, out int size) || size < 0 || size > 6) return;
        ship.gameObject.SetActive(false);
        singleYard.gameObject.SetActive(false);
        if (fleetYard == null) fleetYard = ShipModel.BuildFleetYard(materials, out crane);
        if (fleet == null)
        {
            fleet = new Transform[6];
            for (int i = 0; i < fleet.Length; i++)
            {
                Transform model = ShipModel.Build(materials).transform;
                model.SetParent(fleetYard, false);
                model.position = new Vector3((i % 3 - 1) * 32, i < 3 ? 0 : -1.4f, i < 3 ? -44 : 43);
                model.localScale = Vector3.one * (.76f + (i % 3) * .05f);
                model.localRotation = Quaternion.Euler(0, i < 3 ? 0 : 180, 0);
                fleet[i] = model;
            }
        }
        for (int i = 0; i < fleet.Length; i++) fleet[i].gameObject.SetActive(i < size);
        hoveredSlot = pressedSlot = -1;
        Apply("reset", true);
    }

    void Apply(string view, bool snap)
    {
        float vy, vp, w, h;
        switch (view)
        {
            case "front": vy = 180f; vp = 6f; w = 10f; h = 15f; break;
            case "side": vy = -90f; vp = 6f; w = 33f; h = 15f; break;
            case "top": vy = -90f; vp = 88f; w = 33f; h = 10f; break;
            case "reset": vy = -130f; vp = 35f; w = 49f; h = 32f; break;
            default: return;
        }
        if (fleet != null)
        {
            fleetView = view;
            if (view == "reset" || view == "top") vy = -64f;
            vp = view == "top" ? 88f : 58f;
        }
        float half = Mathf.Tan(cam.fieldOfView * .5f * Mathf.Deg2Rad);
        float aspect = Mathf.Max(cam.aspect, .01f);
        Bounds bounds = fleet == null ? default : FleetBounds();
        tPivot = fleet == null ? DefaultPivot : bounds.center;
        tDist = fleet == null
            ? Mathf.Clamp(Mathf.Max(w / (half * aspect), h / half) * 1.15f, DistMin, DistMax)
            : FitFleet(bounds, vp, vy, half, aspect);
        lastAspect = aspect;
        tPitch = vp;
        if (snap) { tYaw = vy; yaw = tYaw; pitch = tPitch; dist = tDist; pivot = tPivot; Place(); return; }
        // reset은 위치·방향·줌 모두 복구. yaw는 짧은 방향으로.
        tYaw = yaw + Mathf.DeltaAngle(yaw, vy);
    }

    Bounds FleetBounds()
    {
        var bounds = new Bounds(DefaultPivot, Vector3.zero);
        bool found = false;
        foreach (Transform model in fleet)
        {
            if (!model.gameObject.activeSelf) continue;
            foreach (var renderer in model.GetComponentsInChildren<Renderer>())
            {
                if (found) bounds.Encapsulate(renderer.bounds);
                else { bounds = renderer.bounds; found = true; }
            }
        }
        return bounds;
    }

    static float FitFleet(Bounds bounds, float pitch, float yaw, float halfFov, float aspect)
    {
        var inverse = Quaternion.Inverse(Quaternion.Euler(pitch, yaw, 0));
        float distance = DistMin;
        foreach (float x in new[] { -bounds.extents.x, bounds.extents.x })
            foreach (float y in new[] { -bounds.extents.y, bounds.extents.y })
                foreach (float z in new[] { -bounds.extents.z, bounds.extents.z })
                {
                    Vector3 point = inverse * new Vector3(x, y, z);
                    float required = Mathf.Max(Mathf.Abs(point.x) / (halfFov * aspect), Mathf.Abs(point.y) / halfFov);
                    distance = Mathf.Max(distance, required * 1.12f - point.z);
                }
        return distance;
    }

    void Update()
    {
        if (fleet != null && Mathf.Abs(cam.aspect - lastAspect) > .01f)
            Apply(fleetView, false);
        Vector3 m = Input.mousePosition;
        Vector3 d = m - lastMouse;
        lastMouse = m;
        bool fresh = Input.GetMouseButtonDown(0) || Input.GetMouseButtonDown(1);
        if (!fresh)
        {
            if (Input.GetMouseButton(0))
            {
                tYaw += d.x * .3f;
                tPitch = Mathf.Clamp(tPitch - d.y * .25f, PitchMin, PitchMax);
            }
            else if (Input.GetMouseButton(1))
            {
                float perPx = 2f * dist * Mathf.Tan(cam.fieldOfView * .5f * Mathf.Deg2Rad) / Mathf.Max(Screen.height, 1);
                Vector3 move = -(cam.transform.right * d.x + cam.transform.up * d.y) * perPx;
                tPivot = ClampPivot(tPivot + move);
            }
        }
        float wheel = Mathf.Clamp(Input.mouseScrollDelta.y, -3f, 3f);
        if (wheel != 0f) tDist = Mathf.Clamp(tDist * Mathf.Exp(-wheel * .12f), DistMin, Mathf.Max(DistMax, tDist));

        float a = 1f - Mathf.Exp(-K * Time.unscaledDeltaTime);
        yaw = Mathf.Lerp(yaw, tYaw, a);
        pitch = Mathf.Lerp(pitch, tPitch, a);
        dist = Mathf.Lerp(dist, tDist, a);
        pivot = Vector3.Lerp(pivot, tPivot, a);
        if (Mathf.Abs(tYaw - yaw) < 1e-4f) yaw = tYaw;
        if (Mathf.Abs(tPitch - pitch) < 1e-4f) pitch = tPitch;
        if (Mathf.Abs(tDist - dist) < 1e-4f) dist = tDist;
        if ((tPivot - pivot).sqrMagnitude < 1e-8f) pivot = tPivot;
        // 짧은 방향 회전 후 각도를 정규화해 누적을 막는다.
        if (yaw == tYaw && Mathf.Abs(yaw) > 360f) { yaw = Mathf.Repeat(yaw + 180f, 360f) - 180f; tYaw = yaw; }
        Place();
        Transform target = null;
        if (cam.pixelRect.Contains(m) && Physics.Raycast(cam.ScreenPointToRay(m), out RaycastHit hit, cam.farClipPlane))
            target = hit.transform;
        if (fleet != null)
        {
            crane.localPosition = new Vector3(Mathf.Sin(Time.unscaledTime * .45f) * 26f, 19f, -68f);
            int slot = -1;
            for (int i = 0; target != null && i < fleet.Length; i++)
                if (target.IsChildOf(fleet[i])) { slot = i; break; }
            if (Input.GetMouseButtonDown(0)) { press = m; pressedSlot = slot; }
            if (Input.GetMouseButtonUp(0) && slot >= 0 && slot == pressedSlot && (m - press).sqrMagnitude < 36f)
                ShipViewer_FleetEvent(slot, 1);
            if (slot != hoveredSlot)
            {
                hoveredSlot = slot;
                ShipViewer_FleetEvent(slot, 0);
            }
            return;
        }
        bool hitShip = target != null && target.IsChildOf(ship) && !Input.GetMouseButton(0) && !Input.GetMouseButton(1);
        if (hitShip != hovering)
        {
            hovering = hitShip;
            ShipViewer_NotifyHover(hovering ? 1 : 0);
        }
    }

    Vector3 ClampPivot(Vector3 p)
    {
        float limit = fleet == null ? 14f : 110f;
        return new Vector3(Mathf.Clamp(p.x, -limit, limit), Mathf.Clamp(p.y, 2f, 24f), Mathf.Clamp(p.z, -limit, limit));
    }

    void Place()
    {
        var rot = Quaternion.Euler(pitch, yaw, 0f);
        cam.transform.SetPositionAndRotation(pivot - rot * Vector3.forward * dist, rot);
    }
}
