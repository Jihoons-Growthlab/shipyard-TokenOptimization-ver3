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
    const float PitchMin = 4f, PitchMax = 88f, DistMin = 50f, DistMax = 260f;
    static readonly Vector3 DefaultPivot = new Vector3(0f, 7f, 0f);

    float yaw, pitch, dist; Vector3 pivot;          // 현재값
    float tYaw, tPitch, tDist; Vector3 tPivot;     // 목표값
    Vector3 lastMouse;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ShipViewer_NotifyReady();
#else
    static void ShipViewer_NotifyReady() { }
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
        ShipModel.Build(materials);
    }

    IEnumerator Start()
    {
        Apply("reset", true);
        yield return new WaitForEndOfFrame();
        ShipViewer_NotifyReady();
    }

    public void SetView(string view) => Apply(view, false);

    void Apply(string view, bool snap)
    {
        float vy, vp, w, h;
        switch (view)
        {
            case "front": vy = 180f; vp = 6f; w = 10f; h = 15f; break;
            case "side": vy = -90f; vp = 6f; w = 33f; h = 15f; break;
            case "top": vy = -90f; vp = 88f; w = 33f; h = 10f; break;
            case "reset": vy = -130f; vp = 20f; w = 34f; h = 15f; break;
            default: return;
        }
        float half = Mathf.Tan(cam.fieldOfView * .5f * Mathf.Deg2Rad);
        float aspect = Mathf.Max(cam.aspect, .01f);
        tDist = Mathf.Clamp(Mathf.Max(w / (half * aspect), h / half) * 1.15f, DistMin, DistMax);
        tPitch = vp;
        tPivot = DefaultPivot;
        if (snap) { tYaw = vy; yaw = tYaw; pitch = tPitch; dist = tDist; pivot = tPivot; Place(); return; }
        // reset은 위치·방향·줌 모두 복구. yaw는 짧은 방향으로.
        tYaw = yaw + Mathf.DeltaAngle(yaw, vy);
    }

    void Update()
    {
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
        if (wheel != 0f) tDist = Mathf.Clamp(tDist * Mathf.Exp(-wheel * .12f), DistMin, DistMax);

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
    }

    static Vector3 ClampPivot(Vector3 p) =>
        new Vector3(Mathf.Clamp(p.x, -10f, 10f), Mathf.Clamp(p.y, 2f, 14f), Mathf.Clamp(p.z, -14f, 14f));

    void Place()
    {
        var rot = Quaternion.Euler(pitch, yaw, 0f);
        cam.transform.SetPositionAndRotation(pivot - rot * Vector3.forward * dist, rot);
    }
}
