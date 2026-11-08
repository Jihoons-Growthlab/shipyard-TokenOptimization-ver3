using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// 씬·재질을 매번 재생성하고 Web 빌드까지 수행한다.
// Unity -batchmode -quit -buildTarget WebGL -projectPath unity/ShipyardViewer -executeMethod ViewerBuild.Build
public static class ViewerBuild
{
    const string GenDir = "Assets/Generated";
    const string ScenePath = GenDir + "/Viewer.unity";

    static readonly (string name, string hex, float smooth)[] Mats =
    {
        ("HullLower", "#9E2F2A", .3f), ("HullUpper", "#1B3A66", .4f), ("Deck", "#6F8A7A", .2f), ("House", "#E4E8EE", .3f),
        ("Accent", "#D97F2A", .3f), ("Glass", "#202C3C", .8f), ("Steel", "#5B6573", .3f), ("Ground", "#B4BDC9", .05f),
    };

    static string OutDir => Path.GetFullPath(Path.Combine(Application.dataPath, "../../../frontend/public/unity/ship-viewer"));

    public static void Build()
    {
        try
        {
            Run();
            EditorApplication.Exit(0);
        }
        catch (Exception e)
        {
            Debug.LogError("BuildFailedException: " + e);
            EditorApplication.Exit(1);
        }
    }

    static Material[] CreateMaterials()
    {
        if (AssetDatabase.IsValidFolder(GenDir)) AssetDatabase.DeleteAsset(GenDir);
        AssetDatabase.CreateFolder("Assets", "Generated");
        var shader = Shader.Find("Standard") ?? throw new Exception("Standard shader not found");
        return Mats.Select(m =>
        {
            ColorUtility.TryParseHtmlString(m.hex, out var c);
            var mat = new Material(shader) { name = m.name, color = c };
            mat.SetFloat("_Glossiness", m.smooth);
            mat.SetFloat("_Metallic", 0f);
            AssetDatabase.CreateAsset(mat, $"{GenDir}/{m.name}.mat");
            return mat;
        }).ToArray();
    }

    static void CreateScene(Material[] mats)
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        ColorUtility.TryParseHtmlString("#DDE4EE", out var bg);
        cam.backgroundColor = bg;
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 1f;
        cam.farClipPlane = 1000f;

        var sunGo = new GameObject("Sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = .95f;
        sun.shadows = LightShadows.Soft;
        sun.color = Color.white;
        sunGo.transform.rotation = Quaternion.Euler(52f, -35f, 0f);

        RenderSettings.skybox = null;
        RenderSettings.sun = sun;
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);
        RenderSettings.fog = false;
        Lightmapping.bakedGI = false;
        Lightmapping.realtimeGI = false;

        var viewerGo = new GameObject("ShipViewer");
        var viewer = viewerGo.AddComponent<ShipViewer>();
        viewer.cam = cam;
        viewer.materials = mats;

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
    }

    static void ConfigurePlayer()
    {
        var web = NamedBuildTarget.WebGL;
        PlayerSettings.companyName = "SWP";
        PlayerSettings.productName = "ShipyardViewer";
        if (string.IsNullOrEmpty(PlayerSettings.bundleVersion)) PlayerSettings.bundleVersion = "1.0";
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.runInBackground = true;
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.nameFilesAsHashes = false;
        PlayerSettings.WebGL.dataCaching = false;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.None;
        PlayerSettings.WebGL.template = "APPLICATION:Minimal";
        PlayerSettings.stripEngineCode = true;
        PlayerSettings.SetManagedStrippingLevel(web, ManagedStrippingLevel.High);
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.WebGL, new[] { GraphicsDeviceType.OpenGLES3 });
        PlayerSettings.SplashScreen.show = false;
    }

    static void Run()
    {
        var mats = CreateMaterials();
        AssetDatabase.SaveAssets();
        CreateScene(mats);
        ConfigurePlayer();
        AssetDatabase.SaveAssets();

        string outDir = OutDir;
        if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
        Directory.CreateDirectory(Path.GetDirectoryName(outDir));

        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = outDir,
            target = BuildTarget.WebGL,
            options = BuildOptions.None,
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new Exception($"Build {report.summary.result}: {report.summary.totalErrors} errors");

        File.Delete(Path.Combine(outDir, "index.html"));
        string td = Path.Combine(outDir, "TemplateData");
        if (Directory.Exists(td)) Directory.Delete(td, true);

        string buildDir = Path.Combine(outDir, "Build");
        string Find(string suffix) =>
            Directory.GetFiles(buildDir).Select(Path.GetFileName).FirstOrDefault(f => f.EndsWith(suffix, StringComparison.Ordinal))
            ?? throw new Exception("missing build file *" + suffix);
        string json = "{\n" +
            $"  \"loaderUrl\": \"{Find(".loader.js")}\",\n" +
            $"  \"dataUrl\": \"{Find(".data")}\",\n" +
            $"  \"frameworkUrl\": \"{Find(".framework.js")}\",\n" +
            $"  \"codeUrl\": \"{Find(".wasm")}\",\n" +
            $"  \"companyName\": \"{PlayerSettings.companyName}\",\n" +
            $"  \"productName\": \"{PlayerSettings.productName}\",\n" +
            $"  \"productVersion\": \"{PlayerSettings.bundleVersion}\"\n}}\n";
        File.WriteAllText(Path.Combine(buildDir, "build.json"), json);
        long bytes = Directory.GetFiles(buildDir).Sum(f => new FileInfo(f).Length);
        Debug.Log($"Build succeeded: {buildDir} ({bytes / 1048576f:F1} MB)");
    }
}
