/* Tour guiado — segmentos por página, ancorados em [data-tour].
   Auto-inicia no primeiro acesso (window.TOUR.seen === false); o botão
   "Ver tutorial" chama startTour(0). Entre páginas, a continuação vai na
   query ?tour=<indice do segmento>. */
(function () {
  const driver = window.driver.js.driver;

  const SEGMENTS = [
    {
      page: "/app/ocorrencias",
      steps: [
        { popover: { title: "Bem-vindo!", description:
            "Este tour rápido mostra tudo que o sistema faz. Você pode revê-lo " +
            "a qualquer momento no botão “Ver tutorial” da barra lateral." } },
        { element: '[data-tour="nav-ocorrencias"]', popover: { title: "Ocorrências",
            description: "Cruza o PDF de jornada com a planilha de pedido e preenche a coluna MOTIVO." } },
        { element: '[data-tour="oc-pdf"]', popover: { title: "PDF de jornada",
            description: "Envie aqui o relatório PDF de jornada de trabalho." } },
        { element: '[data-tour="oc-xlsx"]', popover: { title: "Planilha de pedido",
            description: "Envie a planilha Excel que receberá os motivos." } },
        { element: '[data-tour="oc-codigos"]', popover: { title: "Códigos de ocorrência",
            description: "Marque quais códigos entram no processamento (FA, AT, FE...)." } },
        { element: '[data-tour="oc-processar"]', popover: { title: "Processar",
            description: "O arquivo entra na fila e a barra de progresso acompanha. Se as duas " +
            "varreduras do PDF divergirem, você revisa as diferenças antes de baixar o resultado." } },
      ],
    },
    {
      page: "/app/vt-caixa",
      steps: [
        { element: '[data-tour="nav-vtcaixa"]', popover: { title: "VT-Caixa",
            description: "Gera o CSV de benefícios a partir da fonte Nautilus e do cadastro." } },
        { element: '[data-tour="vt-fonte"]', popover: { title: "Fonte Nautilus",
            description: "PDF ou Excel do relatório Nautilus." } },
        { element: '[data-tour="vt-cadastral"]', popover: { title: "Cadastro funcional",
            description: "Excel cadastral com CPF, RG, endereço etc." } },
        { element: '[data-tour="vt-processar"]', popover: { title: "Processar",
            description: "Ao concluir, baixe o CSV pronto para o banco." } },
      ],
    },
    {
      page: "/app/codigos",
      steps: [
        { element: '[data-tour="nav-codigos"]', popover: { title: "Códigos",
            description: "Tabelas de referência usadas no VT-Caixa." } },
        { element: '[data-tour="cod-beneficio"]', popover: { title: "Operadora → Código",
            description: "Clique numa linha para copiar o código." } },
        { element: '[data-tour="cod-add-beneficio"]', popover: { title: "Adicionar código",
            description: "Cadastre operadoras novas aqui — elas passam a valer no processamento " +
            "do VT-Caixa para todos os usuários, com prioridade sobre as embutidas." } },
        { element: '[data-tour="cod-depart"]', popover: { title: "Departamentos",
            description: "Substituições de nome de departamento aplicadas no CSV. Também é " +
            "possível adicionar e excluir as personalizadas." } },
      ],
    },
    {
      page: "/app/historico",
      steps: [
        { element: '[data-tour="nav-historico"]', popover: { title: "Histórico",
            description: "Todos os seus processamentos ficam registrados aqui." } },
        { element: '[data-tour="hist-filtros"]', popover: { title: "Busca e filtro",
            description: "Procure por nome de arquivo ou filtre por sucesso/erro." } },
        { element: '[data-tour="hist-export"]', popover: { title: "Exportar",
            description: "Baixe o histórico filtrado em CSV." } },
        { element: '[data-tour="btn-tutorial"]', popover: { title: "Rever o tutorial",
            description: "Fim! Clique aqui sempre que quiser rever este tour." } },
      ],
    },
  ];

  function markSeen() {
    if (window.TOUR.seen) return;
    window.TOUR.seen = true;
    fetch("/app/tutorial/seen", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "csrf_token=" + encodeURIComponent(window.TOUR.csrf),
    });
  }

  function runSegment(idx) {
    const seg = SEGMENTS[idx];
    // pula passos cujo elemento não existe na página (layout pode mudar)
    const steps = seg.steps.filter(
      (s) => !s.element || document.querySelector(s.element)
    );
    if (!steps.length) { nextSegment(idx); return; }
    const d = driver({
      showProgress: true,
      nextBtnText: "Próximo",
      prevBtnText: "Anterior",
      doneBtnText: idx === SEGMENTS.length - 1 ? "Concluir" : "Continuar →",
      steps: steps,
      onDestroyed: () => {
        // driver destruído: ou terminou o segmento (avança) ou fechou no meio
        if (d.hasNextStep()) {
          markSeen();           // fechou no meio: marca e para
        } else {
          nextSegment(idx);     // terminou o segmento: próximo
        }
      },
    });
    d.drive();
  }

  function nextSegment(idx) {
    const next = idx + 1;
    if (next >= SEGMENTS.length) { markSeen(); return; }
    window.location.href = SEGMENTS[next].page + "?tour=" + next;
  }

  window.startTour = function (idx) {
    const seg = SEGMENTS[idx || 0];
    if (window.location.pathname !== seg.page) {
      window.location.href = seg.page + "?tour=" + (idx || 0);
      return;
    }
    runSegment(idx || 0);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const tourParam = params.get("tour");
    if (tourParam !== null) {
      const idx = parseInt(tourParam, 10);
      if (idx >= 0 && idx < SEGMENTS.length) runSegment(idx);
    } else if (window.TOUR && window.TOUR.seen === false) {
      // primeiro acesso: começa do início (navega se não estiver na 1ª página)
      window.startTour(0);
    }
  });
})();
