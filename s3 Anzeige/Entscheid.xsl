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



  <title><xsl:value-of select="/Entscheid/Metainfos/Spider"/> <xsl:value-of select="/Entscheid/Metainfos/Signatur"/> <xsl:value-of select="/Entscheid/Metainfos/Gescheaftsnummer"/></title>

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
	<script>
	  (function() {
	    var cx = '006282428619580867506:dqde6byz0nw';
	    var gcse = document.createElement('script');
	    gcse.type = 'text/javascript';
	    gcse.async = true;
	    gcse.src = 'https://cse.google.com/cse.js?cx=' + cx;
	    var s = document.getElementsByTagName('script')[0];
	    s.parentNode.insertBefore(gcse, s);
	  })();
	</script>
	


</head>

<body id="page-top">
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
    		<h3 class="mb-0">
   			<xsl:element name="img">
   				<xsl:attribute name="height">25px</xsl:attribute><xsl:attribute name="src">https://entscheidsuche.ch/img/<xsl:value-of select="/Entscheid/Metainfos/Kanton"/>.svg</xsl:attribute>
       		</xsl:element>
   			<xsl:element name="a">
   				<xsl:attribute name="href">http://entscheidsuche.ch.s3-website.eu-west-3.amazonaws.com/scraper/<xsl:value-of select="/Entscheid/Metainfos/Spider"/></xsl:attribute>&nbsp;<xsl:value-of select="/Entscheid/Metainfos/Spider"/>
   			</xsl:element>
			</h3>
			<table><tbody>
				<tr>
					<th></th>
					<th>Normiert</th>
					<th>Gelesen</th>
				</tr>
				<tr>
					<td>
						Signatur
					</td>
					<td colspan="2">
						<xsl:value-of select="/Entscheid/Metainfos/Signatur"/>
					</td>
				</tr>
				<tr>
					<td>
						Gericht
					</td>
					<td>
						<xsl:value-of select="/Entscheid/Metainfos/Gericht"/>
					</td>
					<td>
						<xsl:value-of select="//Quelle/Gericht"/>
					</td>
					
				</tr>
				<tr>
					<td>
						Kammer
					</td>
					<td>
						<xsl:value-of select="/Entscheid/Metainfos/Kammer"/>
					</td>
					<td>
						<xsl:value-of select="//Quelle/Kammer"/>
					</td>
				</tr>
				<tr>
					<td>
						Geschäftsnummer
					</td>
					<td colspan="2">
						<xsl:value-of select="/Entscheid/Metainfos/Geschaeftsnummer"/>
					</td>
				</tr>
				<tr>
					<td>
						Entscheiddatum
					</td>
					<td>
						<xsl:value-of select="/Entscheid/Metainfos/EDatum"/>
					</td>
					<xsl:if test="//Sonst/PDatum">
						<td>
							publiziert <xsl:value-of select="//Sonst/PDatum"/>
						</td>
					</xsl:if>		
				</tr>
				<tr>
					<td>
						Verfügbare Formate
					</td>
					<td>
						<xsl:if test="/Entscheid/Metainfos/PDFFile">
							<xsl:element name="a">
								<xsl:attribute name="href">
									../<xsl:value-of select="/Entscheid/Metainfos/PDFFile"/>
								</xsl:attribute>
								<img src="https://pilot.entscheidsuche.ch/pdf.svg" height="25px"/>
							</xsl:element>
						</xsl:if>
						<xsl:if test="/Entscheid/Metainfos/HTMLFile">
							<xsl:element name="a">
								<xsl:attribute name="href">
									../<xsl:value-of select="/Entscheid/Metainfos/HTMLFile"/>
								</xsl:attribute>
								<img src="https://pilot.entscheidsuche.ch/html.svg" height="25px"/>
							</xsl:element>
						</xsl:if>
					</td>
				</tr>
				<xsl:if test="//Sonst/Weiterzug">
					<tr>
						<td>Weiterzug</td>
						<td colspan="2"><xsl:value-of select="//Sonst/Weiterzug"/></td>
					</tr>
				</xsl:if>
				<xsl:if test="//Kurz/Rechtsgebiet">
					<tr>
						<td>Rechtsgebiet</td>
						<td colspan="2"><xsl:value-of select="//Kurz/Rechtsgebiet"/></td>
					</tr>
				</xsl:if>		
				<xsl:if test="//Kurz/Entscheidart">
					<tr>
						<td>Entscheidart</td>
						<td colspan="2"><xsl:value-of select="//Kurz/Entscheidart"/></td>
					</tr>
				</xsl:if>
				<xsl:if test="//Kurz/Titel">
					<tr>
						<td colspan="3"><b><xsl:value-of select="//Kurz/Titel"/></b></td>
					</tr>
				</xsl:if>
				<xsl:if test="//Kurz/Leitsatz">
					<tr>
						<td colspan="3"><xsl:value-of select="//Kurz/Leitsatz"/></td>
					</tr>
				</xsl:if>
						
				
			</tbody></table>
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