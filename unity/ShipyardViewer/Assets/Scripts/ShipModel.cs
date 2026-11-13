using System.Collections.Generic;
using UnityEngine;

// Demo Ship 01: 샘플 형상(실제 호선 아님). 선수 +Z, 지면 y=0.
public static class ShipModel
{
    public enum M { HullLower, HullUpper, Deck, House, Accent, Glass, Steel, Ground }

    public const float Length = 60f, Beam = 10f, Depth = 6f, Keel = 0.8f, Split = 2.6f, Rake = 3f;
    const int Stations = 72;
    static readonly float[] Rows = { 0f, .2f, .5f, .9f, 1.3f, 1.6f, 2.1f, 2.6f, 3.2f, 4f, 5f, 5.6f, 6f };

    public static float HalfWidth(float z, float h)
    {
        float section = 1f - .55f * Mathf.Pow(1f - Mathf.Clamp01(h / 1.6f), 3f);
        float plan = 1f;
        float zs = z - Rake * (h / Depth);
        if (zs > 12f) plan = 1f - Mathf.Pow(Mathf.Clamp01((zs - 12f) / 15f), 2.2f);
        if (z < -18f)
        {
            float s = Mathf.Clamp01((-18f - z) / 12f);
            plan *= 1f - .28f * s * s;
            section *= Mathf.Pow(Mathf.Clamp01((h + .15f) / Depth), .7f * s);
        }
        return Beam / 2f * section * plan;
    }

    class Builder
    {
        public readonly List<Vector3> V = new List<Vector3>();
        public readonly List<int>[] T = { new List<int>(), new List<int>(), new List<int>() };

        public int Add(Vector3 p) { V.Add(p); return V.Count - 1; }

        // 바깥 방향 힌트로 면 방향을 정한다. 0 면적 면은 건너뛴다.
        public void Tri(int sub, int a, int b, int c, Vector3 outward)
        {
            Vector3 n = Vector3.Cross(V[b] - V[a], V[c] - V[a]);
            if (n.sqrMagnitude < 1e-10f) return;
            if (Vector3.Dot(n, outward) < 0f) { int t = b; b = c; c = t; }
            T[sub].Add(a); T[sub].Add(b); T[sub].Add(c);
        }

        public void Quad(int sub, int a, int b, int c, int d, Vector3 outward)
        {
            Tri(sub, a, b, c, outward);
            Tri(sub, a, c, d, outward);
        }
    }

    static float StationZ(int i) => -Length / 2f + Length * i / (Stations - 1);

    public static Mesh HullMesh()
    {
        var b = new Builder();
        int R = Rows.Length;
        // 좌우 현: 현별로 정점을 병합(곡면 법선), x=0에서 공유하지 않는다.
        foreach (float side in new[] { -1f, 1f })
        {
            var idx = new int[Stations, R];
            for (int i = 0; i < Stations; i++)
                for (int j = 0; j < R; j++)
                {
                    float z = StationZ(i), h = Rows[j];
                    idx[i, j] = b.Add(new Vector3(side * HalfWidth(z, h), Keel + h, z));
                }
            var outward = new Vector3(side, 0f, 0f);
            for (int i = 0; i < Stations - 1; i++)
                for (int j = 0; j < R - 1; j++)
                {
                    int sub = (Rows[j] + Rows[j + 1]) / 2f < Split ? 0 : 1;
                    b.Quad(sub, idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1], outward);
                }
        }
        // 바닥·갑판: 각진 면(별도 정점)
        for (int i = 0; i < Stations - 1; i++)
        {
            float z0 = StationZ(i), z1 = StationZ(i + 1);
            foreach (var (h, sub, dir) in new[] { (0f, 0, Vector3.down), (Depth, 2, Vector3.up) })
            {
                float w0 = HalfWidth(z0, h), w1 = HalfWidth(z1, h), y = Keel + h;
                int a = b.Add(new Vector3(-w0, y, z0)), c = b.Add(new Vector3(w0, y, z0));
                int d = b.Add(new Vector3(w1, y, z1)), e = b.Add(new Vector3(-w1, y, z1));
                b.Quad(sub, a, c, d, e, dir);
            }
        }
        // 선미판
        float zt = StationZ(0);
        for (int j = 0; j < R - 1; j++)
        {
            float h0 = Rows[j], h1 = Rows[j + 1];
            float w0 = HalfWidth(zt, h0), w1 = HalfWidth(zt, h1);
            int sub = (h0 + h1) / 2f < Split ? 0 : 1;
            int a = b.Add(new Vector3(-w0, Keel + h0, zt)), c = b.Add(new Vector3(w0, Keel + h0, zt));
            int d = b.Add(new Vector3(w1, Keel + h1, zt)), e = b.Add(new Vector3(-w1, Keel + h1, zt));
            b.Quad(sub, a, c, d, e, Vector3.back);
        }

        var mesh = new Mesh { name = "DemoShip01Hull" };
        mesh.SetVertices(b.V);
        mesh.subMeshCount = 3;
        for (int s = 0; s < 3; s++) mesh.SetTriangles(b.T[s], s);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static Mesh cube;
    static Mesh Cube()
    {
        if (cube != null) return cube;
        var v = new List<Vector3>(); var n = new List<Vector3>(); var t = new List<int>();
        Vector3[] dirs = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
        foreach (var d in dirs)
        {
            Vector3 u = Mathf.Abs(d.y) > .5f ? Vector3.right : Vector3.up;
            Vector3 w = Vector3.Cross(d, u);
            int s = v.Count;
            Vector3 c = d * .5f;
            v.Add(c - u * .5f - w * .5f); v.Add(c + u * .5f - w * .5f); v.Add(c + u * .5f + w * .5f); v.Add(c - u * .5f + w * .5f);
            for (int k = 0; k < 4; k++) n.Add(d);
            int[] q = { s, s + 1, s + 2, s, s + 2, s + 3 };
            Vector3 fn = Vector3.Cross(v[s + 1] - v[s], v[s + 2] - v[s]);
            if (Vector3.Dot(fn, d) < 0) q = new[] { s, s + 2, s + 1, s, s + 3, s + 2 };
            t.AddRange(q);
        }
        cube = new Mesh { name = "Box" };
        cube.SetVertices(v); cube.SetNormals(n); cube.SetTriangles(t, 0);
        cube.RecalculateBounds();
        return cube;
    }

    static GameObject Box(Transform parent, string name, Vector3 center, Vector3 size, Material mat)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = center;
        go.transform.localScale = size;
        go.AddComponent<MeshFilter>().sharedMesh = Cube();
        go.AddComponent<BoxCollider>();
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
        return go;
    }

    // 바닥면 y와 높이로 상자를 놓는다.
    static GameObject Stack(Transform p, string name, float x, float y0, float z, Vector3 size, Material m) =>
        Box(p, name, new Vector3(x, y0 + size.y / 2f, z), size, m);

    public static GameObject Build(Material[] mats)
    {
        Material Mat(M m) => mats[(int)m];
        var root = new GameObject("Ship");
        var t = root.transform;

        var hull = new GameObject("Hull");
        hull.transform.SetParent(t, false);
        var mesh = HullMesh();
        hull.AddComponent<MeshFilter>().sharedMesh = mesh;
        hull.AddComponent<MeshCollider>().sharedMesh = mesh;
        hull.AddComponent<MeshRenderer>().sharedMaterials = new[] { Mat(M.HullLower), Mat(M.HullUpper), Mat(M.Deck) };

        float deck = Keel + Depth;

        // 3단 선실(z≈-20)
        float y = deck;
        var tiers = new[] { new Vector3(9f, 2.6f, 7.4f), new Vector3(8.4f, 2.4f, 6.6f), new Vector3(7.8f, 2.4f, 5.6f) };
        float[] tz = { -19.6f, -20.0f, -20.4f };
        for (int k = 0; k < tiers.Length; k++)
        {
            var s = tiers[k];
            Stack(t, $"House{k + 1}", 0f, y, tz[k], s, Mat(M.House));
            float wy = y + s.y * .55f;
            Box(t, $"WinFront{k + 1}", new Vector3(0f, wy, tz[k] + s.z / 2f + .03f), new Vector3(s.x * .7f, .45f, .08f), Mat(M.Glass));
            Box(t, $"WinPort{k + 1}", new Vector3(-s.x / 2f - .03f, wy, tz[k]), new Vector3(.08f, .45f, s.z * .7f), Mat(M.Glass));
            Box(t, $"WinStbd{k + 1}", new Vector3(s.x / 2f + .03f, wy, tz[k]), new Vector3(.08f, .45f, s.z * .7f), Mat(M.Glass));
            y += s.y;
        }
        // 브리지(최상단) + 윙
        var bridge = new Vector3(7.2f, 2.0f, 4.2f);
        float bz = -19.4f;
        Stack(t, "Bridge", 0f, y, bz, bridge, Mat(M.House));
        Box(t, "BridgeWindows", new Vector3(0f, y + 1.15f, bz + bridge.z / 2f + .03f), new Vector3(bridge.x * .9f, .7f, .08f), Mat(M.Glass));
        Stack(t, "BridgeWings", 0f, y + 1.9f, bz + .2f, new Vector3(11.6f, .25f, 2.6f), Mat(M.House));
        Box(t, "WingWindows", new Vector3(0f, y + 1.15f, bz - bridge.z / 2f - .03f), new Vector3(bridge.x * .8f, .5f, .08f), Mat(M.Glass));
        float roof = y + 2.15f;
        // 마스트
        Stack(t, "Mast", 0f, roof, bz, new Vector3(.22f, 3.2f, .22f), Mat(M.Steel));
        Box(t, "MastYard", new Vector3(0f, roof + 2.3f, bz), new Vector3(2.4f, .16f, .16f), Mat(M.Steel));

        // 오렌지 굴뚝(z=-25)
        Stack(t, "Funnel", 0f, deck, -25f, new Vector3(2.6f, roof - deck - .3f, 3.2f), Mat(M.Accent));
        Stack(t, "FunnelCap", 0f, roof - .3f, -25f, new Vector3(2.8f, .4f, 3.4f), Mat(M.Steel));

        // 해치 4개: 오렌지 코밍 + 강재 덮개
        for (int k = 0; k < 4; k++)
        {
            float z = -9.5f + 8.2f * k;
            Stack(t, $"Coaming{k + 1}", 0f, deck, z, new Vector3(6.6f, .8f, 6.4f), Mat(M.Accent));
            Stack(t, $"Cover{k + 1}", 0f, deck + .8f, z, new Vector3(6.1f, .22f, 5.9f), Mat(M.Steel));
        }

        // 카고 포스트 3개 + 지브
        float[] posts = { -13.4f, 2.8f, 19.2f };
        for (int k = 0; k < posts.Length; k++)
        {
            Stack(t, $"CargoPost{k + 1}", 0f, deck, posts[k], new Vector3(.8f, 5.4f, .8f), Mat(M.Steel));
            Box(t, $"CargoJib{k + 1}", new Vector3(0f, deck + 5.2f, posts[k] + 3.2f), new Vector3(.3f, .3f, 6.2f), Mat(M.Steel));
        }

        // 지면·킬 블록
        for (int k = 0; k < 9; k++)
            Stack(t, $"KeelBlock{k + 1}", 0f, 0f, -24f + 6f * k, new Vector3(1.6f, Keel, 1.2f), Mat(M.Steel));

        return root;
    }

    public static Transform BuildYard(Material[] mats)
    {
        var yard = new GameObject("Shipyard").transform;
        Material Mat(M m) => mats[(int)m];
        Box(yard, "Harbor", new Vector3(0, -2, 0), new Vector3(500, 1, 500), Mat(M.HullUpper));
        Box(yard, "Dry dock floor", new Vector3(0, -.6f, 0), new Vector3(25, 1.2f, 84), Mat(M.Ground));
        foreach (float side in new[] { -1f, 1f })
        {
            Box(yard, "Quay", new Vector3(side * 23, 0, -6), new Vector3(21, 3, 96), Mat(M.Ground));
            Box(yard, "Dock edge", new Vector3(side * 13, 1.55f, -6), new Vector3(.35f, .1f, 96), Mat(M.Accent));
            foreach (float z in new[] { -27f, -21f })
                Box(yard, "Crane leg", new Vector3(side * 14, 11, z), new Vector3(2, 20, 2), Mat(M.Accent));
        }
        Box(yard, "Gantry beam", new Vector3(0, 22, -24), new Vector3(33, 2, 4), Mat(M.Accent));
        Box(yard, "Workshop", new Vector3(24, 5, 10), new Vector3(14, 7, 24), Mat(M.House));
        Box(yard, "Workshop roof", new Vector3(24, 8.7f, 10), new Vector3(15, .5f, 25), Mat(M.Steel));
        for (int row = 0; row < 3; row++)
            Box(yard, "Container", new Vector3(-23, 2.8f, 8 + row * 5), new Vector3(10, 2.6f, 3), Mat(row == 1 ? M.Steel : M.HullLower));
        return yard;
    }

    public static Transform BuildFleetYard(Material[] mats, out Transform trolley)
    {
        var yard = new GameObject("Fleet yard").transform;
        Material Mat(M m) => mats[(int)m];
        Box(yard, "Harbor", new Vector3(0, -3, 0), new Vector3(700, 1, 700), Mat(M.HullUpper));
        Box(yard, "Quay", new Vector3(0, -.5f, 0), new Vector3(124, 2, 22), Mat(M.Ground));
        Box(yard, "Quay stripe", new Vector3(0, .54f, 10), new Vector3(119, .08f, .45f), Mat(M.Accent));
        for (int i = -1; i <= 1; i++)
        {
            float x = i * 32;
            Box(yard, "Dry dock", new Vector3(x, -.5f, -44), new Vector3(26, 1, 72), Mat(M.Ground));
            Box(yard, "Pier", new Vector3(x + 12, -.75f, 43), new Vector3(3, 2.5f, 68), Mat(M.Ground));
            for (int j = 0; j < 3; j++)
                Box(yard, "Freight container", new Vector3(x + j * 4, 1.75f, 1), new Vector3(3.5f, 2.5f, 6), Mat(j == 1 ? M.Steel : M.HullLower));
        }
        foreach (float x in new[] { -58f, 58f })
        {
            Box(yard, "Gantry foundation", new Vector3(x, -.5f, -68), new Vector3(12, 2, 24), Mat(M.Ground));
            Box(yard, "Gantry leg", new Vector3(x, 11, -68), new Vector3(3, 22, 3), Mat(M.Accent));
        }
        Box(yard, "Gantry beam", new Vector3(0, 22, -68), new Vector3(120, 2, 4), Mat(M.Accent));
        trolley = new GameObject("Moving trolley").transform;
        trolley.SetParent(yard, false);
        Box(trolley, "Trolley", Vector3.zero, new Vector3(5, 3, 5), Mat(M.Steel));
        Box(trolley, "Hoist cable", new Vector3(0, -4, 0), new Vector3(.22f, 7, .22f), Mat(M.Steel));
        Box(trolley, "Spreader", new Vector3(0, -8, 0), new Vector3(4, 1, 2), Mat(M.Accent));
        return yard;
    }
}
