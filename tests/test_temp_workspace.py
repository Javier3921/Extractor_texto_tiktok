from src.utils import TempWorkspace


class TestTempWorkspace:
    def test_se_borra_en_exito_por_defecto(self, tmp_path):
        with TempWorkspace(tmp_path, "job_1") as workdir:
            pass  # nunca se llama a mark_ok()
        # sin mark_ok(): se trata como fallo -> se conserva por keep_on_error
        assert workdir.exists()

    def test_se_borra_en_exito_marcado_ok(self, tmp_path):
        ws = TempWorkspace(tmp_path, "job_2")
        with ws as workdir:
            ws.mark_ok()
        assert not workdir.exists()

    def test_always_keep_conserva_aunque_todo_vaya_bien(self, tmp_path):
        ws = TempWorkspace(tmp_path, "job_3", always_keep=True)
        with ws as workdir:
            ws.mark_ok()
        assert workdir.exists()

    def test_keep_on_error_false_borra_incluso_si_falla(self, tmp_path):
        ws = TempWorkspace(tmp_path, "job_4", keep_on_error=False)
        try:
            with ws as workdir:
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert not workdir.exists()
