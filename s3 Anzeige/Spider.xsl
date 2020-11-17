<?xml version="1.0"?>
<!DOCTYPE html [
   <!ENTITY nbsp "&#160;">
]>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="html"/>

  <xsl:template match="/">
<html lang="en">

<head>
	<meta charset="utf-8"/>
	<meta name="viewport" content="width=device-width, initial-scale=1"/>
    <meta name="topic" content="Entscheide"/>
    <meta name="topic" content="Urteile"/>
    <meta name="topic" content="arrêts"/>
    <meta name="topic" content="Schweiz"/>
    <meta name="topic" content="Kantone"/>
    <meta name="topic" content="Bundesgericht"/>
    <meta name="author" content="entscheidsuche.ch"/>

<script src="/get_count.js"></script>

<script>
  function get_counts(){
	<xsl:for-each select="/Spiderliste/Kanton/Spider">
		get_count_json('<xsl:value-of select="@Name"/>');
	</xsl:for-each>	
  }
  
</script>



  <title>Spiderliste</title>

  <!-- Bootstrap core CSS -->
  <link href="https://entscheidsuche.ch/vendor/bootstrap/css/bootstrap.min.css" rel="stylesheet"/>

  <!-- Custom fonts for this template -->
  <link href="https://fonts.googleapis.com/css?family=Saira+Extra+Condensed:500,700" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/css?family=Muli:400,400i,800,800i" rel="stylesheet"/>
  <link href="https://entscheidsuche.ch/vendor/fontawesome-free/css/all.min.css" rel="stylesheet"/>

  <!-- Custom styles for this template -->
  <link href="https://entscheidsuche.ch/css/resume.min.css" rel="stylesheet"/>
  <style type="text/css">
            body, html
            {
                height: 100%;
            }
  </style>	


</head>

<body id="page-top" onload="get_counts();">
  <nav class="navbar navbar-expand-lg navbar-dark bg-primary fixed-top" id="sideNav">
    <a class="navbar-brand js-scroll-trigger" href="#page-top">
      <span class="d-block d-lg-none">entscheidsuche.ch</span>
      <span class="d-none d-lg-block">
        <img class="img-fluid mx-auto" src="https://entscheidsuche.ch/img/entscheidsuche.gif" alt=""/>
      </span>
    </a>
    <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarSupportedContent">
      <ul class="navbar-nav">
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch#suche">Suche</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch/kantone">kantonale Entscheide</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch/bund">Entscheide der Bundesgerichte</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch#aboutDE">Über uns</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch#aboutFR">À propos de nous</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch#support">Wer uns unterstützt</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="https://entscheidsuche.ch#mitglied">Mitglied werden</a>
        </li>
        <li class="nav-item">
          <a class="nav-link js-scroll-trigger" href="entscheidsuche-statuten.pdf">Statuten</a>
        </li>
      </ul>
    </div>
  </nav>
	      <section class="resume-section p-3 p-lg-5 d-flex justify-content-center" id="urteile">
    	  <div class="w-100">
    		<h3 class="mb-0">Spiderliste (<span id="total">0</span> Entscheide)</h3>
    		<xsl:for-each select="/Spiderliste/Kanton">
    			<h3 class="mb-0">
		   			<xsl:element name="img">
   						<xsl:attribute name="height">25px</xsl:attribute><xsl:attribute name="src">https://entscheidsuche.ch/img/<xsl:value-of select="@Kurz"/>.svg</xsl:attribute>
       				</xsl:element>
    				&nbsp;
	    			<xsl:value-of select="@Name"/>
	    		</h3>
					<xsl:for-each select="Spider">
						<b>
								<xsl:element name="a">
									<xsl:attribute name="href">http://entscheidsuche.ch.s3-website.eu-west-3.amazonaws.com/scraper/<xsl:value-of select="@Name"/>/</xsl:attribute>
									<xsl:value-of select="@Name"/>
								</xsl:element>
							</b>
							<xsl:if test="Eintrag/Parameter">
								<xsl:text> Parameter: </xsl:text><xsl:value-of select="Eintrag/Parameter"/>="<xsl:value-of select="Eintrag/Format"/>" <i>[<xsl:value-of select="Eintrag/Bedeutung"/>]</i>
							</xsl:if>
							<xsl:element name="div">
								<xsl:attribute name="id"><xsl:value-of select="@Name"/></xsl:attribute>
								???
							</xsl:element>																		
							<table class="table">
								<tbody>
									<xsl:for-each select="Eintrag">
										<tr>
											<td valign="top" align="left">
												<xsl:element name="a">
													<xsl:attribute name="href">http://entscheidsuche.ch.s3-website.eu-west-3.amazonaws.com/scraper/<xsl:value-of select="../@Name"/>/<xsl:value-of select="Signatur"/></xsl:attribute>
													<xsl:choose>
														<xsl:when test="substring-after(@Name,'_99')='9'">
															<b>
																<font color="green"><xsl:value-of select="@Name"/></font>
															</b>
														</xsl:when>
														<xsl:otherwise>
															<b>
																<xsl:value-of select="@Name"/>
															</b>
														</xsl:otherwise>
													</xsl:choose>
												</xsl:element>
												<br/>
												<xsl:element name="div">
													<xsl:attribute name="id"><xsl:value-of select="@Name"/></xsl:attribute>
													???
												</xsl:element>											
											</td>
											<td valign="top" align="left">
												<i>
													<xsl:value-of select="Stufe_2_DE"/>
													<xsl:if test="Stufe_2_DE and Stufe_2_FR"><br/></xsl:if><xsl:value-of select="Stufe_2_FR"/>
													<xsl:if test="Stufe_2_IT and (Stufe_2_DE or Stufe_2_FR)"><br/></xsl:if><xsl:value-of select="Stufe_2_IT"/>
												</i>
											</td>
											<td valign="top" align="left">
												<font color="blue">
													<xsl:value-of select="Stufe_3_DE"/>
													<xsl:if test="Stufe_3_DE and Stufe_3_FR"><br/></xsl:if><xsl:value-of select="Stufe_3_FR"/>
													<xsl:if test="Stufe_3_IT and (Stufe_3_DE or Stufe_3_FR)"><br/></xsl:if><xsl:value-of select="Stufe_3_IT"/>
												</font>
											</td>
											<td valign="top" align="left">
												<font color="red">
													<xsl:if test="Matching"><xsl:text> </xsl:text></xsl:if><xsl:value-of select="Matching"/>
												</font>
											</td>
										</tr>
									</xsl:for-each>
								</tbody>
							</table>
 						
					</xsl:for-each>
				
	    	</xsl:for-each>
		</div>
		</section>

  <!-- Bootstrap core JavaScript -->
  <script src="https://entscheidsuche.ch/vendor/jquery/jquery.min.js"></script>
  <script src="https://entscheidsuche.ch/vendor/bootstrap/js/bootstrap.bundle.min.js"></script>

  <!-- Plugin JavaScript -->
  <script src="https://entscheidsuche.ch/vendor/jquery-easing/jquery.easing.min.js"></script>

  <!-- Custom scripts for this template -->
  <script src="https://entscheidsuche.ch/js/resume.min.js"></script>

</body>

</html>
</xsl:template>
</xsl:stylesheet>